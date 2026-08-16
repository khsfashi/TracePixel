from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

from .gallery import STATIC_HTML_GALLERY_SCHEMA_V1, StaticHtmlGallery

MOBILE_REVIEW_PACKAGE_SCHEMA_V1 = "tracepixel.mobile-review-package.v1"


class MobileReviewPackageContractError(ValueError):
    """Stable rejection for malformed P6-V5 mobile review package input."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


@dataclass(frozen=True, slots=True)
class MobileReviewPackage:
    manifest: dict[str, object]
    html_en: bytes
    html_ko: bytes


def _fail(code: str, path: str, message: str) -> None:
    raise MobileReviewPackageContractError(code, path, message)


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


def _replace_once(document: str, old: str, new: str, *, path: str) -> str:
    count = document.count(old)
    if count != 1:
        _fail(
            "source_html_drift",
            path,
            f"expected exactly one source token, found {count}: {old!r}",
        )
    return document.replace(old, new, 1)


def _source_stage_linkage(gallery: StaticHtmlGallery) -> str:
    if gallery.manifest.get("schema") != STATIC_HTML_GALLERY_SCHEMA_V1:
        _fail(
            "unsupported_gallery_schema",
            "$.gallery.manifest.schema",
            f"expected {STATIC_HTML_GALLERY_SCHEMA_V1!r}",
        )
    gallery_record = gallery.manifest.get("gallery")
    if type(gallery_record) is not dict:
        _fail("invalid_gallery_manifest", "$.gallery.manifest.gallery", "must be an object")
    typed_gallery = cast(dict[str, object], gallery_record)
    if typed_gallery.get("size_bytes") != len(gallery.html):
        _fail("gallery_size_mismatch", "$.gallery.html", "size does not match V3 manifest")
    if typed_gallery.get("sha256") != sha256(gallery.html).hexdigest():
        _fail("gallery_digest_mismatch", "$.gallery.html", "SHA-256 does not match V3 manifest")

    sources = gallery.manifest.get("sources")
    if type(sources) is not dict:
        _fail("invalid_gallery_manifest", "$.gallery.manifest.sources", "must be an object")
    stage_source = cast(dict[str, object], sources).get("stage_contact_sheet")
    if type(stage_source) is not dict:
        _fail(
            "invalid_gallery_manifest",
            "$.gallery.manifest.sources.stage_contact_sheet",
            "must be an object",
        )
    linkage = cast(dict[str, object], stage_source).get("linkage")
    if linkage not in ("separate-reference", "bundle-stage-artifacts"):
        _fail(
            "invalid_stage_linkage",
            "$.gallery.manifest.sources.stage_contact_sheet.linkage",
            "must be separate-reference or bundle-stage-artifacts",
        )
    return cast(str, linkage)


def _inject_mobile_css(document: str) -> str:
    css = """
.language-switch { display: flex; align-items: center; gap: 8px; margin-top: 12px; font-size: .9rem; }
.language-switch a { color: inherit; font-weight: 700; text-underline-offset: 3px; }
.language-switch .current { font-weight: 800; }
.provenance { margin: 0 0 12px; border: 2px solid color-mix(in srgb, CanvasText 36%, transparent); border-radius: 12px; padding: 11px 12px; line-height: 1.4; }
.provenance strong { display: block; margin-bottom: 4px; }
.provenance p { margin: 0; font-size: .86rem; }
.stage-sheet { width: 100%; }
.source-language-note { margin-top: 8px; font-size: .8rem; opacity: .7; }
""".strip()
    return _replace_once(
        document,
        "@media (min-width: 700px)",
        css + "\n@media (min-width: 700px)",
        path="$.gallery.html.style",
    )


def _render_english(base: str, stage_linkage: str) -> str:
    document = _inject_mobile_css(base)
    document = _replace_once(
        document,
        "</header>",
        '<nav class="language-switch" aria-label="Language"><span class="current">English</span><span aria-hidden="true">·</span><a href="index.ko.html" lang="ko">한국어</a></nav>\n</header>',
        path="$.gallery.html.header",
    )
    stage_image_token = '<img src="data:image/svg+xml;base64,'
    first = document.find(stage_image_token)
    second = document.find(stage_image_token, first + len(stage_image_token))
    if first < 0 or second < 0:
        _fail("source_html_drift", "$.gallery.html.stage_svg", "expected two embedded SVG images")
    document = document[:second] + document[second:].replace(
        stage_image_token,
        '<img class="stage-sheet" src="data:image/svg+xml;base64,',
        1,
    )

    if stage_linkage == "separate-reference":
        heading = "Stage workflow reference"
        notice = (
            '<div class="provenance provenance-warning" data-stage-linkage="separate-reference">'
            '<strong>Reference stages — not provenance of this final output</strong>'
            '<p>The frozen final-output bundle contains no stage-image records. This contact sheet is separate committed workflow evidence, so visual differences from the final output are expected.</p>'
            '</div>'
        )
        caption = (
            "Separate committed stage workflow reference. Do not interpret these frames as the exact intermediate states of the final image above."
        )
    else:
        heading = "Stage progression evidence"
        notice = (
            '<div class="provenance provenance-linked" data-stage-linkage="bundle-stage-artifacts">'
            '<strong>Linked stages — exact bundle provenance</strong>'
            '<p>Every displayed stage image matches a stage-image record in the final preview bundle by source path and SHA-256.</p>'
            '</div>'
        )
        caption = "These stage frames are exactly linked to stage-image records in the preview bundle."

    document = _replace_once(
        document,
        '<h2 id="stages-title">Stage progression evidence</h2>\n<figure>',
        f'<h2 id="stages-title">{heading}</h2>\n{notice}\n<figure>',
        path="$.gallery.html.stages",
    )
    old_caption = (
        "This bundle declares no stage images; the sheet is separate committed review evidence."
        if stage_linkage == "separate-reference"
        else "This sheet is linked to stage-image records in the preview bundle."
    )
    document = _replace_once(
        document,
        old_caption,
        caption,
        path="$.gallery.html.stage_caption",
    )
    return document


def _render_korean(base: str, stage_linkage: str, qa_status: str, finding_count: object, complexity_recorded: bool) -> str:
    document = _render_english(base, stage_linkage)
    replacements = (
        ('<html lang="en">', '<html lang="ko">'),
        ("TracePixel static review", "TracePixel 정적 검토"),
        ("self-contained P6-V3 evidence view", "독립형 P6-V3 증거 보기"),
        (
            '<nav class="language-switch" aria-label="Language"><span class="current">English</span><span aria-hidden="true">·</span><a href="index.ko.html" lang="ko">한국어</a></nav>',
            '<nav class="language-switch" aria-label="언어"><a href="index.html" lang="en">English</a><span aria-hidden="true">·</span><span class="current">한국어</span></nav>',
        ),
        (">Stages</span>", ">단계</span>"),
        (">Complexity</span>", ">복잡도</span>"),
        (">Canvas</span>", ">캔버스</span>"),
        ("Final output", "최종 결과"),
        ("Nearest-neighbor final pixel-art preview", "최근접 이웃 방식으로 확대한 최종 픽셀 아트 미리보기"),
        (
            "Exact P6-V0 preview PNG bytes embedded as a data URI. Gallery layout is presentation-only.",
            "P6-V0 확대 미리보기 PNG 바이트를 그대로 data URI로 포함합니다. 갤러리 레이아웃은 표시 전용입니다.",
        ),
        ("Deterministic QA + Agent metrics", "결정론적 QA + Agent 지표"),
        ("TracePixel QA and Agent complexity composition", "TracePixel QA 및 Agent 복잡도 구성"),
        ("TracePixel authored-stage contact sheet", "TracePixel 작성 단계 contact sheet"),
        (
            "Deterministic QA remains source evidence. Agent complexity remains observational.",
            "결정론적 QA는 원본 증거의 권위를 유지하며, Agent 복잡도는 관측 지표입니다.",
        ),
        ("Task / intent", "작업 / 의도"),
        ("Authority boundary", "근거 권한 경계"),
        ("Raster truth:", "래스터 진실값:"),
        ("unchanged; this page embeds existing preview evidence.", "변경하지 않으며, 이 페이지는 기존 미리보기 증거를 포함할 뿐입니다."),
        ("Deterministic QA:", "결정론적 QA:"),
        ("source evidence from the P6-V0/V2 contract.", "P6-V0/V2 계약의 원본 증거입니다."),
        ("<strong>Stage + metrics compositions:</strong> presentation-only.", "<strong>단계 + 지표 구성:</strong> 표시 전용입니다."),
        ("Perceptual/VLM:", "지각/VLM:"),
        ("not included; unresolved G4 is not crossed.", "포함하지 않으며, 미해결 G4를 넘지 않습니다."),
        ("Human judgment:", "사람의 판단:"),
        ("final aesthetic judgment is not encoded as machine truth.", "최종 미적 판단을 기계적 진실값으로 기록하지 않습니다."),
        ("Network/runtime:", "네트워크/런타임:"),
        ("no external assets, scripts, server, provider call, GPU, or self-hosted runner required.", "외부 에셋, 스크립트, 서버, provider 호출, GPU, self-hosted runner가 필요하지 않습니다."),
    )
    for old, new in replacements:
        document = _replace_once(document, old, new, path="$.localized.ko")

    english_qa = f"{qa_status} · {finding_count} findings"
    korean_qa = f"{qa_status} · 발견 {finding_count}건"
    document = _replace_once(document, english_qa, korean_qa, path="$.localized.ko.qa_badge")
    complexity_text = "recorded" if complexity_recorded else "not available"
    complexity_ko = "기록됨" if complexity_recorded else "없음"
    document = _replace_once(
        document,
        f">{complexity_text}</strong>",
        f">{complexity_ko}</strong>",
        path="$.localized.ko.complexity_badge",
    )

    if stage_linkage == "separate-reference":
        stage_replacements = (
            ("Stage workflow reference", "단계 작업 흐름 참고 자료"),
            ("Reference stages — not provenance of this final output", "참고 단계 — 이 최종 결과의 실제 생성 이력이 아닙니다"),
            (
                "The frozen final-output bundle contains no stage-image records. This contact sheet is separate committed workflow evidence, so visual differences from the final output are expected.",
                "현재 frozen 최종 결과 bundle에는 stage-image 기록이 없습니다. 아래 contact sheet는 별도로 커밋된 작업 흐름 참고 자료이므로 최종 결과와 시각적으로 다른 것이 정상입니다.",
            ),
            (
                "Separate committed stage workflow reference. Do not interpret these frames as the exact intermediate states of the final image above.",
                "별도로 커밋된 단계 작업 흐름 참고 자료입니다. 위 최종 이미지의 정확한 중간 상태로 해석하면 안 됩니다.",
            ),
        )
    else:
        stage_replacements = (
            ("Stage progression evidence", "단계 진행 증거"),
            ("Linked stages — exact bundle provenance", "연결된 단계 — 정확한 bundle 생성 이력"),
            (
                "Every displayed stage image matches a stage-image record in the final preview bundle by source path and SHA-256.",
                "표시된 모든 단계 이미지는 source path와 SHA-256 기준으로 최종 preview bundle의 stage-image 기록과 일치합니다.",
            ),
            (
                "These stage frames are exactly linked to stage-image records in the preview bundle.",
                "이 단계 프레임들은 preview bundle의 stage-image 기록과 정확히 연결되어 있습니다.",
            ),
        )
    for old, new in stage_replacements:
        document = _replace_once(document, old, new, path="$.localized.ko.stages")

    document = _replace_once(
        document,
        "</figure>\n</section>\n<section aria-labelledby=\"intent-title\">",
        '</figure>\n<p class="source-language-note">단계 이름과 아래 JSON 스키마 키는 원본 증거 식별자를 보존하기 위해 영어 원문을 유지합니다.</p>\n</section>\n<section aria-labelledby="intent-title">',
        path="$.localized.ko.source_note",
    )
    return document


def build_mobile_review_package(gallery: StaticHtmlGallery) -> MobileReviewPackage:
    """Layer deterministic bilingual mobile-review pages over a verified P6-V3 gallery."""

    if not isinstance(gallery, StaticHtmlGallery):
        _fail("invalid_gallery", "$.gallery", "must be StaticHtmlGallery")
    stage_linkage = _source_stage_linkage(gallery)
    try:
        base = gallery.html.decode("utf-8")
    except UnicodeDecodeError as exc:
        _fail("invalid_gallery_html", "$.gallery.html", f"must be UTF-8: {exc}")

    sources = cast(dict[str, object], gallery.manifest["sources"])
    metrics = cast(dict[str, object], sources["qa_metrics"])
    qa_status = str(metrics.get("qa_status", "unknown")).upper()
    finding_count = metrics.get("finding_count", "?")

    complexity_recorded = ">recorded</strong>" in base
    html_en = _render_english(base, stage_linkage).encode("utf-8")
    html_ko = _render_korean(
        base,
        stage_linkage,
        qa_status,
        finding_count,
        complexity_recorded,
    ).encode("utf-8")

    source_manifest = _canonical_json_bytes(gallery.manifest)
    manifest: dict[str, object] = {
        "schema": MOBILE_REVIEW_PACKAGE_SCHEMA_V1,
        "source_gallery": {
            "schema": STATIC_HTML_GALLERY_SCHEMA_V1,
            "manifest_sha256": sha256(source_manifest).hexdigest(),
            "html_sha256": sha256(gallery.html).hexdigest(),
        },
        "stage_linkage": stage_linkage,
        "pages": {
            "en": {
                "path": "index.html",
                "language": "en",
                "media_type": "text/html; charset=utf-8",
                "size_bytes": len(html_en),
                "sha256": sha256(html_en).hexdigest(),
                "companion": "index.ko.html",
            },
            "ko": {
                "path": "index.ko.html",
                "language": "ko",
                "media_type": "text/html; charset=utf-8",
                "size_bytes": len(html_ko),
                "sha256": sha256(html_ko).hexdigest(),
                "companion": "index.html",
            },
        },
        "presentation": {
            "scripts": 0,
            "external_dependencies": 0,
            "runtime_language_switch": False,
            "static_language_pages": ["en", "ko"],
        },
        "authority": {
            "raster_truth": "unchanged",
            "deterministic_qa": "source-evidence",
            "stage_composition": "presentation-only",
            "localization": "presentation-only",
            "perceptual": "not-included",
            "human_judgment": "not-recorded",
        },
    }
    _canonical_json_bytes(manifest)
    return MobileReviewPackage(manifest=manifest, html_en=html_en, html_ko=html_ko)


def write_mobile_review_package(package: MobileReviewPackage, output_dir: str | Path) -> None:
    """Materialize one bilingual P6-V5 mobile review package without stale files."""

    if not isinstance(package, MobileReviewPackage):
        _fail("invalid_package", "$.package", "must be MobileReviewPackage")
    root = Path(output_dir)
    if root.exists():
        if not root.is_dir():
            _fail("output_not_directory", "$.output_dir", "must be a directory path")
        if any(root.iterdir()):
            _fail("output_not_empty", "$.output_dir", "refusing to overwrite a non-empty directory")
    else:
        root.mkdir(parents=True)

    root.joinpath("index.html").write_bytes(package.html_en)
    root.joinpath("index.ko.html").write_bytes(package.html_ko)
    root.joinpath("manifest.json").write_bytes(_canonical_json_bytes(package.manifest))
