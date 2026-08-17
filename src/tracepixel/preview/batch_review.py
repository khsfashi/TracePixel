from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Sequence

BATCH_REVIEW_PACKAGE_SCHEMA_V1 = "tracepixel.batch-review-package.v1"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ALLOWED_SOURCE_KINDS = frozenset(("retained-output", "presentation-fixture"))


class BatchReviewPackageContractError(ValueError):
    """Stable rejection for malformed batch-review package input."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


@dataclass(frozen=True, slots=True)
class BatchReviewMember:
    member_id: str
    asset_class: str
    width: int
    height: int
    png: bytes
    source_kind: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class BatchReviewTilePlacement:
    member_id: str
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class BatchReviewPackage:
    manifest: dict[str, object]
    html_en: bytes
    html_ko: bytes


def _fail(code: str, path: str, message: str) -> None:
    raise BatchReviewPackageContractError(code, path, message)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail("non_json_value", "$", f"must be canonical JSON-compatible data: {exc}")


def _png_dimensions(png: bytes, path: str) -> tuple[int, int]:
    if not isinstance(png, bytes):
        _fail("invalid_png_type", path, "png must be immutable bytes")
    if len(png) < 24 or png[:8] != _PNG_SIGNATURE:
        _fail("invalid_png", path, "must begin with the PNG signature and IHDR")
    if png[12:16] != b"IHDR":
        _fail("invalid_png", path, "first PNG chunk must be IHDR")
    width, height = struct.unpack(">II", png[16:24])
    if width <= 0 or height <= 0:
        _fail("invalid_png_dimensions", path, "IHDR dimensions must be positive")
    return width, height


def _validate_member(member: BatchReviewMember, index: int) -> None:
    path = f"$.members[{index}]"
    if not isinstance(member, BatchReviewMember):
        _fail("invalid_member", path, "must be BatchReviewMember")
    if not member.member_id or member.member_id.strip() != member.member_id:
        _fail("invalid_member_id", f"{path}.member_id", "must be a non-empty trimmed string")
    if not member.asset_class or member.asset_class.strip() != member.asset_class:
        _fail("invalid_asset_class", f"{path}.asset_class", "must be a non-empty trimmed string")
    if type(member.width) is not int or type(member.height) is not int:
        _fail("invalid_dimensions", path, "width and height must be exact integers")
    if member.width <= 0 or member.height <= 0:
        _fail("invalid_dimensions", path, "width and height must be positive")
    if member.source_kind not in _ALLOWED_SOURCE_KINDS:
        _fail(
            "invalid_source_kind",
            f"{path}.source_kind",
            "must be retained-output or presentation-fixture",
        )
    if not member.source_ref or member.source_ref.strip() != member.source_ref:
        _fail("invalid_source_ref", f"{path}.source_ref", "must be a non-empty trimmed string")
    png_width, png_height = _png_dimensions(member.png, f"{path}.png")
    if (png_width, png_height) != (member.width, member.height):
        _fail(
            "png_dimension_mismatch",
            f"{path}.png",
            f"IHDR is {png_width}x{png_height}, expected {member.width}x{member.height}",
        )


def _validate_tile_layout(
    placements: Sequence[BatchReviewTilePlacement],
    member_by_id: dict[str, BatchReviewMember],
) -> tuple[int, int]:
    if not placements:
        return 0, 0

    coords: set[tuple[int, int]] = set()
    tile_member_ids: set[str] = set()
    max_x = -1
    max_y = -1
    tile_size: tuple[int, int] | None = None
    for index, placement in enumerate(placements):
        path = f"$.tile_layout[{index}]"
        if not isinstance(placement, BatchReviewTilePlacement):
            _fail("invalid_tile_placement", path, "must be BatchReviewTilePlacement")
        if placement.member_id not in member_by_id:
            _fail("unknown_tile_member", f"{path}.member_id", "must reference one declared member")
        if placement.member_id in tile_member_ids:
            _fail("duplicate_tile_member", f"{path}.member_id", "tile member may appear only once")
        if type(placement.x) is not int or type(placement.y) is not int:
            _fail("invalid_tile_coordinate", path, "x and y must be exact integers")
        if placement.x < 0 or placement.y < 0:
            _fail("invalid_tile_coordinate", path, "x and y must be non-negative")
        coord = (placement.x, placement.y)
        if coord in coords:
            _fail("duplicate_tile_coordinate", path, "tile coordinate must be unique")

        member = member_by_id[placement.member_id]
        if member.asset_class != "terrain-tile":
            _fail(
                "invalid_tile_asset_class",
                f"{path}.member_id",
                "tile layout may contain only terrain-tile members",
            )
        current_size = (member.width, member.height)
        if tile_size is None:
            tile_size = current_size
        elif tile_size != current_size:
            _fail("mixed_tile_size", path, "all tile-layout members must share one exact size")

        coords.add(coord)
        tile_member_ids.add(placement.member_id)
        max_x = max(max_x, placement.x)
        max_y = max(max_y, placement.y)

    columns = max_x + 1
    rows = max_y + 1
    expected = {(x, y) for y in range(rows) for x in range(columns)}
    if coords != expected:
        _fail("sparse_tile_layout", "$.tile_layout", "tile layout must fill its bounding grid exactly")
    return columns, rows


def _image_uri(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "title": "TracePixel P8 batch review",
            "subtitle": "Mobile-safe per-member and tile-set evidence",
            "language": "Language",
            "companion": "한국어",
            "members": "Per-member outputs",
            "native": "Native 1x",
            "inspect": "Nearest-neighbor inspection",
            "tiles": "Tile patch",
            "authority": "Evidence authority boundary",
            "deterministic": "Deterministic",
            "deterministic_text": "member identity, class, dimensions, PNG SHA-256, retained source reference, and declared tile placement.",
            "perceptual": "Perceptual / human",
            "perceptual_text": "recognizability, native-1x readability, cross-asset style coherence, palette coherence, tile pixel seams, and repetition quality.",
            "fixture": "Presentation fixture",
            "fixture_text": "This package contains presentation fixtures. They prove the review surface only and must not be used as production-quality evidence.",
            "retained": "Retained output",
            "retained_text": "These images are retained authoring outputs. Human judgments may be recorded as perceptual evidence, never deterministic QA truth.",
            "checklist": "Human review checklist",
            "check_style": "Cross-asset style coherence",
            "check_palette": "Palette coherence",
            "check_seam": "Tile pixel seam quality",
            "check_readability": "Native-1x readability",
            "check_mobile": "Mobile scanability",
            "source": "Source",
            "sha": "PNG SHA-256",
            "class": "Class",
            "canvas": "Canvas",
        }
    if language == "ko":
        return {
            "title": "TracePixel P8 배치 검토",
            "subtitle": "모바일에서 보는 멤버별 결과와 타일셋 증거",
            "language": "언어",
            "companion": "English",
            "members": "멤버별 결과",
            "native": "원본 1배",
            "inspect": "최근접 이웃 확대 확인",
            "tiles": "타일 패치",
            "authority": "증거 권한 경계",
            "deterministic": "결정론적으로 확인하는 항목",
            "deterministic_text": "멤버 ID, 클래스, 크기, PNG SHA-256, 보존된 원본 참조, 선언된 타일 배치입니다.",
            "perceptual": "사람이 시각적으로 판단하는 항목",
            "perceptual_text": "무엇인지 알아보기 쉬운지, 원본 1배 가독성, 에셋 간 스타일/팔레트 일관성, 타일 픽셀 이음새와 반복 품질입니다.",
            "fixture": "표시용 fixture",
            "fixture_text": "이 패키지는 표시용 fixture를 포함합니다. 검토 화면의 동작만 증명하며 실제 생성 품질의 근거로 사용하면 안 됩니다.",
            "retained": "보존된 실제 결과",
            "retained_text": "이 이미지는 보존된 작성 결과입니다. 사람의 평가는 지각 증거로만 기록하며 결정론적 QA 진실값으로 승격하지 않습니다.",
            "checklist": "사람이 확인할 항목",
            "check_style": "에셋 간 스타일 일관성",
            "check_palette": "팔레트 일관성",
            "check_seam": "타일 픽셀 이음새 품질",
            "check_readability": "원본 1배 가독성",
            "check_mobile": "모바일에서 훑어보기 쉬운지",
            "source": "원본",
            "sha": "PNG SHA-256",
            "class": "클래스",
            "canvas": "캔버스",
        }
    _fail("unsupported_language", "$.language", "must be en or ko")


def _html_page(
    members: Sequence[BatchReviewMember],
    placements: Sequence[BatchReviewTilePlacement],
    *,
    language: str,
    review_scope: str,
) -> bytes:
    labels = _labels(language)
    companion = "index.ko.html" if language == "en" else "index.html"
    current = "English" if language == "en" else "한국어"

    cards: list[str] = []
    image_class_by_id: dict[str, str] = {}
    image_rules: list[str] = []
    for index, member in enumerate(members):
        image_class = f"member-image-{index}"
        image_class_by_id[member.member_id] = image_class
        image_rules.append(f'.{image_class}{{background-image:url("{_image_uri(member.png)}")}}')
        digest = sha256(member.png).hexdigest()
        cards.append(
            '<article class="member-card" data-member-id="' + member.member_id + '">'
            f'<h3>{member.member_id}</h3>'
            '<div class="member-meta">'
            f'<span>{labels["class"]}: <code>{member.asset_class}</code></span>'
            f'<span>{labels["canvas"]}: <code>{member.width}×{member.height}</code></span>'
            "</div>"
            '<div class="member-images">'
            f'<figure><figcaption>{labels["native"]}</figcaption>'
            f'<div class="native-box"><span class="pixel-image native-image {image_class}" '
            f'style="--source-width:{member.width}px;--source-height:{member.height}px" '
            f'role="img" aria-label="{member.member_id}"></span></div></figure>'
            f'<figure><figcaption>{labels["inspect"]}</figcaption>'
            f'<div class="pixel-image pixel-preview {image_class}" '
            f'style="aspect-ratio:{member.width}/{member.height}" '
            f'role="img" aria-label="{member.member_id}"></div></figure>'
            "</div>"
            '<dl class="evidence">'
            f'<dt>{labels["source"]}</dt><dd><code>{member.source_ref}</code></dd>'
            f'<dt>{labels["sha"]}</dt><dd><code>{digest}</code></dd>'
            "</dl>"
            "</article>"
        )

    tile_html = ""
    if placements:
        columns = max(p.x for p in placements) + 1
        tiles = "".join(
            f'<div class="pixel-image tile {image_class_by_id[p.member_id]}" role="img" '
            f'aria-label="{p.member_id}" style="grid-column:{p.x + 1};grid-row:{p.y + 1}"></div>'
            for p in placements
        )
        tile_html = (
            f'<section aria-labelledby="tiles-title"><h2 id="tiles-title">{labels["tiles"]}</h2>'
            f'<p class="section-note">{labels["perceptual_text"]}</p>'
            f'<div class="tile-patch" style="--tile-columns:{columns}">{tiles}</div></section>'
        )

    scope_title = labels["retained"] if review_scope == "retained-output" else labels["fixture"]
    scope_text = labels["retained_text"] if review_scope == "retained-output" else labels["fixture_text"]
    lang_attr = "ko" if language == "ko" else "en"

    document = f"""<!doctype html>
<html lang="{lang_attr}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark light">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; object-src 'none'">
<title>{labels["title"]}</title>
<style>
{''.join(image_rules)}
*{{box-sizing:border-box}}body{{font-family:system-ui,-apple-system,sans-serif;margin:0;background:Canvas;color:CanvasText}}main{{max-width:980px;margin:auto;padding:14px 14px 64px}}header{{padding:8px 0 18px}}h1{{font-size:1.5rem;margin:.2rem 0}}h2{{font-size:1.2rem;margin:30px 0 12px}}h3{{font-size:1rem;margin:0 0 9px;overflow-wrap:anywhere}}p{{line-height:1.5}}.subtitle,.section-note{{opacity:.76}}.language-switch{{display:flex;gap:8px;align-items:center;font-size:.9rem}}.language-switch a{{color:inherit;font-weight:700}}.scope,.authority,.checklist{{border:1px solid color-mix(in srgb,CanvasText 28%,transparent);border-radius:14px;padding:13px 14px;margin:14px 0}}.scope strong,.authority strong{{display:block;margin-bottom:4px}}.member-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px}}.member-card{{border:1px solid color-mix(in srgb,CanvasText 24%,transparent);border-radius:14px;padding:13px;min-width:0}}.member-meta{{display:flex;flex-wrap:wrap;gap:6px 12px;font-size:.82rem;opacity:.8}}.member-images{{display:grid;grid-template-columns:92px 1fr;gap:12px;align-items:end;margin-top:12px}}figure{{margin:0;min-width:0}}figcaption{{font-size:.78rem;opacity:.72;margin-bottom:6px}}.native-box{{height:80px;display:flex;align-items:center;justify-content:center;border-radius:10px;background:color-mix(in srgb,CanvasText 8%,transparent)}}.pixel-image{{background-repeat:no-repeat;background-position:center;background-size:100% 100%;image-rendering:pixelated;image-rendering:crisp-edges}}.native-image{{display:block;width:var(--source-width);height:var(--source-height)}}.pixel-preview{{width:min(100%,192px);display:block;border-radius:10px;background-color:color-mix(in srgb,CanvasText 8%,transparent)}}.evidence{{font-size:.76rem;margin:12px 0 0}}.evidence dt{{font-weight:700;margin-top:6px}}.evidence dd{{margin:2px 0;overflow-wrap:anywhere}}code{{font-family:ui-monospace,SFMono-Regular,monospace;font-size:.92em}}.tile-patch{{display:grid;grid-template-columns:repeat(var(--tile-columns),minmax(0,96px));width:max-content;max-width:100%;gap:0;border:1px solid color-mix(in srgb,CanvasText 35%,transparent);background:color-mix(in srgb,CanvasText 8%,transparent)}}.tile{{width:96px;height:96px;max-width:24vw;max-height:24vw}}.authority-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.checklist ul{{margin:.4rem 0 0;padding-left:1.25rem;line-height:1.65}}@media(max-width:560px){{.member-grid{{grid-template-columns:1fr}}.authority-grid{{grid-template-columns:1fr}}.member-images{{grid-template-columns:78px 1fr}}.tile{{width:22vw;height:22vw}}}}
</style>
</head>
<body>
<main data-review-scope="{review_scope}">
<header>
<h1>{labels["title"]}</h1><p class="subtitle">{labels["subtitle"]}</p>
<nav class="language-switch" aria-label="{labels["language"]}"><strong>{current}</strong><span aria-hidden="true">·</span><a href="{companion}">{labels["companion"]}</a></nav>
<div class="scope" data-source-kind="{review_scope}"><strong>{scope_title}</strong><p>{scope_text}</p></div>
</header>
<section aria-labelledby="members-title"><h2 id="members-title">{labels["members"]}</h2><div class="member-grid">{''.join(cards)}</div></section>
{tile_html}
<section aria-labelledby="authority-title"><h2 id="authority-title">{labels["authority"]}</h2><div class="authority authority-grid"><div><strong>{labels["deterministic"]}</strong><p>{labels["deterministic_text"]}</p></div><div><strong>{labels["perceptual"]}</strong><p>{labels["perceptual_text"]}</p></div></div></section>
<section class="checklist" aria-labelledby="check-title"><h2 id="check-title">{labels["checklist"]}</h2><ul><li>{labels["check_style"]}</li><li>{labels["check_palette"]}</li><li>{labels["check_seam"]}</li><li>{labels["check_readability"]}</li><li>{labels["check_mobile"]}</li></ul></section>
</main>
</body>
</html>"""
    return document.encode("utf-8")


def build_batch_review_package(
    members: Sequence[BatchReviewMember],
    *,
    tile_layout: Sequence[BatchReviewTilePlacement] = (),
) -> BatchReviewPackage:
    """Build a bilingual, network-free batch review package over retained member PNG bytes."""

    if not isinstance(members, Sequence) or isinstance(members, (str, bytes, bytearray)):
        _fail("invalid_members", "$.members", "must be an ordered sequence")
    if not members:
        _fail("empty_members", "$.members", "at least one member is required")

    member_by_id: dict[str, BatchReviewMember] = {}
    for index, member in enumerate(members):
        _validate_member(member, index)
        if member.member_id in member_by_id:
            _fail("duplicate_member_id", f"$.members[{index}].member_id", "must be unique")
        member_by_id[member.member_id] = member

    if not isinstance(tile_layout, Sequence) or isinstance(tile_layout, (str, bytes, bytearray)):
        _fail("invalid_tile_layout", "$.tile_layout", "must be an ordered sequence")
    columns, rows = _validate_tile_layout(tile_layout, member_by_id)

    source_kinds = {member.source_kind for member in members}
    review_scope = "retained-output" if source_kinds == {"retained-output"} else "presentation-fixture"

    manifest_members = [
        {
            "member_id": member.member_id,
            "asset_class": member.asset_class,
            "canvas": {"width": member.width, "height": member.height},
            "png_sha256": sha256(member.png).hexdigest(),
            "png_size_bytes": len(member.png),
            "source_kind": member.source_kind,
            "source_ref": member.source_ref,
        }
        for member in members
    ]
    manifest: dict[str, object] = {
        "schema": BATCH_REVIEW_PACKAGE_SCHEMA_V1,
        "review_scope": review_scope,
        "members": manifest_members,
        "tile_layout": {
            "columns": columns,
            "rows": rows,
            "placements": [
                {"member_id": p.member_id, "x": p.x, "y": p.y}
                for p in tile_layout
            ],
        },
        "presentation": {
            "languages": ["en", "ko"],
            "scripts": 0,
            "external_dependencies": 0,
            "image_embedding": "data-uri-original-png",
            "inspection_scaling": "css-nearest-neighbor",
        },
        "authority": {
            "deterministic": [
                "member-identity",
                "asset-class",
                "canvas-dimensions",
                "png-sha256",
                "source-reference",
                "declared-tile-placement",
            ],
            "perceptual_only": [
                "recognizability",
                "native-1x-readability",
                "cross-asset-style-coherence",
                "palette-coherence",
                "tile-pixel-seam-quality",
                "tile-repetition-quality",
                "mobile-scanability",
            ],
            "human_judgment_is_deterministic_qa": False,
        },
    }

    html_en = _html_page(
        members,
        tile_layout,
        language="en",
        review_scope=review_scope,
    )
    html_ko = _html_page(
        members,
        tile_layout,
        language="ko",
        review_scope=review_scope,
    )
    manifest["pages"] = {
        "index.html": {"sha256": sha256(html_en).hexdigest(), "size_bytes": len(html_en)},
        "index.ko.html": {"sha256": sha256(html_ko).hexdigest(), "size_bytes": len(html_ko)},
    }
    return BatchReviewPackage(manifest=manifest, html_en=html_en, html_ko=html_ko)


def validate_batch_review_package(package: BatchReviewPackage) -> None:
    if not isinstance(package, BatchReviewPackage):
        _fail("invalid_package", "$", "must be BatchReviewPackage")
    manifest = package.manifest
    if manifest.get("schema") != BATCH_REVIEW_PACKAGE_SCHEMA_V1:
        _fail("invalid_schema", "$.manifest.schema", "unexpected package schema")
    if manifest.get("review_scope") not in _ALLOWED_SOURCE_KINDS:
        _fail("invalid_review_scope", "$.manifest.review_scope", "unexpected review scope")
    presentation = manifest.get("presentation")
    if type(presentation) is not dict:
        _fail("invalid_presentation", "$.manifest.presentation", "must be an object")
    if presentation.get("scripts") != 0 or presentation.get("external_dependencies") != 0:
        _fail("unsafe_presentation", "$.manifest.presentation", "must remain script/network independent")
    if presentation.get("image_embedding") != "data-uri-original-png":
        _fail("presentation_drift", "$.manifest.presentation.image_embedding", "must reuse original PNG bytes")
    if presentation.get("inspection_scaling") != "css-nearest-neighbor":
        _fail("presentation_drift", "$.manifest.presentation.inspection_scaling", "must avoid generated enlarged rasters")

    pages = manifest.get("pages")
    if type(pages) is not dict:
        _fail("invalid_pages", "$.manifest.pages", "must be an object")
    for name, data in (("index.html", package.html_en), ("index.ko.html", package.html_ko)):
        record = pages.get(name)
        if type(record) is not dict:
            _fail("missing_page_record", f"$.manifest.pages.{name}", "page record missing")
        if record.get("sha256") != sha256(data).hexdigest() or record.get("size_bytes") != len(data):
            _fail("page_digest_mismatch", f"$.manifest.pages.{name}", "page bytes do not match manifest")

    manifest_members = manifest.get("members")
    if type(manifest_members) is not list:
        _fail("invalid_manifest_members", "$.manifest.members", "must be an array")
    for language, page, companion in (
        ("en", package.html_en, "index.ko.html"),
        ("ko", package.html_ko, "index.html"),
    ):
        try:
            text = page.decode("utf-8")
        except UnicodeDecodeError as exc:
            _fail("invalid_html_encoding", f"$.html_{language}", f"must be UTF-8: {exc}")
        if f'<html lang="{language}">' not in text:
            _fail("html_language_mismatch", f"$.html_{language}", "html lang is missing")
        if 'name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"' not in text:
            _fail("mobile_viewport_missing", f"$.html_{language}", "mobile viewport is missing")
        if f'href="{companion}"' not in text:
            _fail("language_switch_missing", f"$.html_{language}", "static companion language link is missing")
        lowered = text.lower()
        if "<script" in lowered or "http://" in lowered or "https://" in lowered:
            _fail("unsafe_html", f"$.html_{language}", "scripts and network URLs are forbidden")
        for raw_member in manifest_members:
            if type(raw_member) is not dict:
                _fail("invalid_manifest_member", "$.manifest.members", "member records must be objects")
            member_id = raw_member.get("member_id")
            if type(member_id) is not str or f'data-member-id="{member_id}"' not in text:
                _fail("member_missing_from_page", f"$.html_{language}", f"{member_id!r} is missing")
        if 'id="authority-title"' not in text or 'id="check-title"' not in text:
            _fail("review_cues_missing", f"$.html_{language}", "authority/checklist cues are missing")


def write_batch_review_package(package: BatchReviewPackage, output: Path) -> None:
    """Write one validated package into a new/empty directory."""

    validate_batch_review_package(package)
    if output.exists():
        if not output.is_dir():
            _fail("invalid_output", "$.output", "must be a directory")
        if any(output.iterdir()):
            _fail("nonempty_output", "$.output", "must be empty")
    else:
        output.mkdir(parents=True)

    (output / "index.html").write_bytes(package.html_en)
    (output / "index.ko.html").write_bytes(package.html_ko)
    (output / "manifest.json").write_bytes(_canonical_json_bytes(package.manifest) + b"\n")
