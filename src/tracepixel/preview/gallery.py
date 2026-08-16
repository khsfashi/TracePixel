from __future__ import annotations

import base64
import html
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

from .bundle import PREVIEW_BUNDLE_SCHEMA_V1, PreviewBundle
from .contact_sheet import STAGE_CONTACT_SHEET_SCHEMA_V1, StageContactSheet
from .qa_metrics import QA_METRICS_COMPOSITION_SCHEMA_V1, QaMetricsComposition

STATIC_HTML_GALLERY_SCHEMA_V1 = "tracepixel.static-html-gallery.v1"


class StaticHtmlGalleryContractError(ValueError):
    """Stable deterministic rejection for malformed P6-V3 gallery input."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


@dataclass(frozen=True, slots=True)
class StaticHtmlGallery:
    manifest: dict[str, object]
    html: bytes


def _fail(code: str, path: str, message: str) -> None:
    raise StaticHtmlGalleryContractError(code, path, message)


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


def _record(
    manifest: dict[str, object],
    key: str,
    path: str,
    *,
    expected_media_type: str,
) -> dict[str, object]:
    value = manifest.get(key)
    if type(value) is not dict:
        _fail("invalid_manifest_record", path, "must be a file record object")
    record = cast(dict[object, object], value)
    if not all(type(item) is str for item in record):
        _fail("invalid_manifest_record", path, "record keys must be strings")
    typed = cast(dict[str, object], record)
    for field in ("path", "media_type", "size_bytes", "sha256"):
        if field not in typed:
            _fail("invalid_manifest_record", path, f"missing required field {field!r}")
    if typed["media_type"] != expected_media_type:
        _fail(
            "unexpected_media_type",
            f"{path}.media_type",
            f"expected {expected_media_type!r}",
        )
    recorded_path = typed["path"]
    if type(recorded_path) is not str or not recorded_path:
        _fail("invalid_manifest_record", f"{path}.path", "must be a non-empty string")
    size_bytes = typed["size_bytes"]
    if type(size_bytes) is not int or size_bytes < 0:
        _fail(
            "invalid_manifest_record",
            f"{path}.size_bytes",
            "must be a non-negative integer",
        )
    digest = typed["sha256"]
    if type(digest) is not str or len(digest) != 64:
        _fail(
            "invalid_manifest_record",
            f"{path}.sha256",
            "must be a SHA-256 hex digest",
        )
    return typed


def _bundle_file(
    bundle: PreviewBundle,
    key: str,
    path: str,
    *,
    expected_media_type: str,
) -> tuple[dict[str, object], bytes]:
    record = _record(
        bundle.manifest,
        key,
        path,
        expected_media_type=expected_media_type,
    )
    recorded_path = cast(str, record["path"])
    try:
        data = bundle.file_bytes(recorded_path)
    except KeyError:
        _fail("missing_bundle_file", path, f"bundle is missing {recorded_path!r}")
    if len(data) != record["size_bytes"]:
        _fail("source_size_mismatch", path, f"size does not match {recorded_path!r}")
    if sha256(data).hexdigest() != record["sha256"]:
        _fail("source_digest_mismatch", path, f"SHA-256 does not match {recorded_path!r}")
    return record, data


def _json_object(data: bytes, path: str) -> dict[str, object]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("invalid_json_evidence", path, f"must be UTF-8 JSON: {exc}")
    if type(value) is not dict:
        _fail("invalid_json_evidence", path, "must decode to a JSON object")
    root = cast(dict[object, object], value)
    if not all(type(key) is str for key in root):
        _fail("invalid_json_evidence", path, "object keys must be strings")
    return cast(dict[str, object], root)


def _validate_embedded_svg(
    manifest: dict[str, object],
    data: bytes,
    *,
    schema: str,
    record_key: str,
    path: str,
    record_has_path: bool,
) -> dict[str, object]:
    if manifest.get("schema") != schema:
        _fail("unsupported_source_schema", f"{path}.schema", f"expected {schema!r}")
    value = manifest.get(record_key)
    if type(value) is not dict:
        _fail("invalid_manifest_record", f"{path}.{record_key}", "must be a record object")
    record = cast(dict[str, object], value)
    if record.get("media_type") != "image/svg+xml":
        _fail(
            "unexpected_media_type",
            f"{path}.{record_key}.media_type",
            "expected 'image/svg+xml'",
        )
    if record_has_path:
        recorded_path = record.get("path")
        if type(recorded_path) is not str or not recorded_path:
            _fail(
                "invalid_manifest_record",
                f"{path}.{record_key}.path",
                "must be a non-empty string",
            )
    expected_size = record.get("size_bytes")
    if type(expected_size) is not int or expected_size < 0:
        _fail(
            "invalid_manifest_record",
            f"{path}.{record_key}.size_bytes",
            "must be a non-negative integer",
        )
    expected_digest = record.get("sha256")
    if type(expected_digest) is not str or len(expected_digest) != 64:
        _fail(
            "invalid_manifest_record",
            f"{path}.{record_key}.sha256",
            "must be a SHA-256 hex digest",
        )
    if len(data) != expected_size:
        _fail("source_size_mismatch", path, "embedded SVG size does not match its manifest")
    if sha256(data).hexdigest() != expected_digest:
        _fail("source_digest_mismatch", path, "embedded SVG digest does not match its manifest")
    return record


def _validate_qa_linkage(
    bundle: PreviewBundle,
    composition: QaMetricsComposition,
    preview_record: dict[str, object],
    qa_record: dict[str, object],
) -> None:
    manifest = composition.manifest
    if manifest.get("source_bundle_schema") != PREVIEW_BUNDLE_SCHEMA_V1:
        _fail(
            "qa_bundle_schema_mismatch",
            "$.qa_metrics.manifest.source_bundle_schema",
            f"expected {PREVIEW_BUNDLE_SCHEMA_V1!r}",
        )

    image = manifest.get("image")
    if type(image) is not dict:
        _fail("invalid_qa_linkage", "$.qa_metrics.manifest.image", "must be an object")
    image_record = cast(dict[str, object], image)
    if image_record.get("path") != preview_record["path"] or image_record.get("sha256") != preview_record["sha256"]:
        _fail(
            "qa_preview_mismatch",
            "$.qa_metrics.manifest.image",
            "must reference the same preview PNG as the gallery bundle",
        )

    qa_value = manifest.get("deterministic_qa")
    if type(qa_value) is not dict:
        _fail(
            "invalid_qa_linkage",
            "$.qa_metrics.manifest.deterministic_qa",
            "must be an object",
        )
    qa_link = cast(dict[str, object], qa_value)
    if qa_link.get("path") != qa_record["path"] or qa_link.get("sha256") != qa_record["sha256"]:
        _fail(
            "qa_evidence_mismatch",
            "$.qa_metrics.manifest.deterministic_qa",
            "must reference the same deterministic QA evidence as the gallery bundle",
        )

    complexity_record = bundle.manifest.get("complexity_evidence")
    complexity_link = manifest.get("agent_complexity")
    if complexity_record is None:
        if complexity_link is not None:
            _fail(
                "complexity_evidence_mismatch",
                "$.qa_metrics.manifest.agent_complexity",
                "must be null when the gallery bundle has no complexity evidence",
            )
        return
    if type(complexity_record) is not dict or type(complexity_link) is not dict:
        _fail(
            "complexity_evidence_mismatch",
            "$.qa_metrics.manifest.agent_complexity",
            "must reference the gallery bundle complexity evidence",
        )
    source = cast(dict[str, object], complexity_record)
    linked = cast(dict[str, object], complexity_link)
    if linked.get("path") != source.get("path") or linked.get("sha256") != source.get("sha256"):
        _fail(
            "complexity_evidence_mismatch",
            "$.qa_metrics.manifest.agent_complexity",
            "must reference the same complexity evidence as the gallery bundle",
        )


def _stage_linkage(bundle: PreviewBundle, sheet: StageContactSheet) -> str:
    raw_artifacts = bundle.manifest.get("stage_artifacts")
    if type(raw_artifacts) is not list:
        _fail("invalid_stage_artifacts", "$.bundle.manifest.stage_artifacts", "must be an array")
    source_images: dict[str, str] = {}
    for index, value in enumerate(raw_artifacts):
        if type(value) is not dict:
            _fail(
                "invalid_stage_artifacts",
                f"$.bundle.manifest.stage_artifacts[{index}]",
                "must be an object",
            )
        record = cast(dict[str, object], value)
        if record.get("kind") == "stage-image":
            source_path = record.get("path")
            digest = record.get("sha256")
            if type(source_path) is not str or type(digest) is not str:
                _fail(
                    "invalid_stage_artifacts",
                    f"$.bundle.manifest.stage_artifacts[{index}]",
                    "stage images require string path and SHA-256",
                )
            source_images[source_path] = digest

    raw_frames = sheet.manifest.get("frames")
    if type(raw_frames) is not list or not raw_frames:
        _fail("invalid_stage_sheet", "$.stage_contact_sheet.manifest.frames", "must be a non-empty array")
    if not source_images:
        return "separate-reference"

    if len(source_images) != len(raw_frames):
        _fail(
            "stage_source_mismatch",
            "$.stage_contact_sheet.manifest.frames",
            "frame count must match bundle stage-image artifacts when the bundle declares them",
        )
    for index, value in enumerate(raw_frames):
        if type(value) is not dict:
            _fail(
                "invalid_stage_sheet",
                f"$.stage_contact_sheet.manifest.frames[{index}]",
                "must be an object",
            )
        frame = cast(dict[str, object], value)
        source_path = frame.get("source_path")
        source_digest = frame.get("source_sha256")
        if type(source_path) is not str or source_images.get(source_path) != source_digest:
            _fail(
                "stage_source_mismatch",
                f"$.stage_contact_sheet.manifest.frames[{index}]",
                "must match one bundle stage-image path and digest",
            )
    return "bundle-stage-artifacts"


def _badge(label: str, value: str) -> str:
    return (
        '<div class="badge"><span class="badge-label">'
        f"{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>"
    )


def build_static_html_gallery(
    bundle: PreviewBundle,
    stage_contact_sheet: StageContactSheet,
    qa_metrics: QaMetricsComposition,
) -> StaticHtmlGallery:
    """Build one deterministic, dependency-free phone-friendly review page."""

    if not isinstance(bundle, PreviewBundle):
        _fail("invalid_bundle", "$.bundle", "must be PreviewBundle")
    if not isinstance(stage_contact_sheet, StageContactSheet):
        _fail("invalid_stage_contact_sheet", "$.stage_contact_sheet", "must be StageContactSheet")
    if not isinstance(qa_metrics, QaMetricsComposition):
        _fail("invalid_qa_metrics", "$.qa_metrics", "must be QaMetricsComposition")
    if bundle.manifest.get("schema") != PREVIEW_BUNDLE_SCHEMA_V1:
        _fail(
            "unsupported_bundle_schema",
            "$.bundle.manifest.schema",
            f"expected {PREVIEW_BUNDLE_SCHEMA_V1!r}",
        )

    canonical_bundle_manifest = _canonical_json_bytes(bundle.manifest)
    try:
        materialized_bundle_manifest = bundle.file_bytes("manifest.json")
    except KeyError:
        _fail("missing_bundle_manifest", "$.bundle.files", "bundle must contain manifest.json")
    if materialized_bundle_manifest != canonical_bundle_manifest:
        _fail(
            "bundle_manifest_mismatch",
            "$.bundle.files.manifest.json",
            "must match the canonical in-memory bundle manifest",
        )

    preview_record, preview_png = _bundle_file(
        bundle,
        "preview_png",
        "$.bundle.manifest.preview_png",
        expected_media_type="image/png",
    )
    intent_record, intent_bytes = _bundle_file(
        bundle,
        "intent_summary",
        "$.bundle.manifest.intent_summary",
        expected_media_type="application/json",
    )
    qa_record, _ = _bundle_file(
        bundle,
        "deterministic_qa",
        "$.bundle.manifest.deterministic_qa",
        expected_media_type="application/json",
    )
    intent = _json_object(intent_bytes, "$.bundle.intent_summary")

    sheet_record = _validate_embedded_svg(
        stage_contact_sheet.manifest,
        stage_contact_sheet.svg,
        schema=STAGE_CONTACT_SHEET_SCHEMA_V1,
        record_key="sheet",
        path="$.stage_contact_sheet.manifest",
        record_has_path=True,
    )
    composition_record = _validate_embedded_svg(
        qa_metrics.manifest,
        qa_metrics.svg,
        schema=QA_METRICS_COMPOSITION_SCHEMA_V1,
        record_key="composition",
        path="$.qa_metrics.manifest",
        record_has_path=False,
    )
    _validate_qa_linkage(bundle, qa_metrics, preview_record, qa_record)
    stage_linkage = _stage_linkage(bundle, stage_contact_sheet)

    qa_summary = qa_metrics.manifest.get("deterministic_qa")
    assert type(qa_summary) is dict
    qa_summary_typed = cast(dict[str, object], qa_summary)
    qa_status = str(qa_summary_typed.get("status", "unknown")).upper()
    finding_count = qa_summary_typed.get("finding_count", "?")

    frames = stage_contact_sheet.manifest.get("frames")
    assert type(frames) is list
    complexity = qa_metrics.manifest.get("agent_complexity")
    complexity_status = "recorded" if complexity is not None else "not available"

    asset_class = str(intent.get("asset_class", "unspecified"))
    canvas = intent.get("canvas")
    canvas_label = "unspecified"
    if type(canvas) is dict:
        canvas_typed = cast(dict[str, object], canvas)
        width = canvas_typed.get("width")
        height = canvas_typed.get("height")
        if type(width) is int and type(height) is int:
            canvas_label = f"{width} × {height}"

    intent_pretty = json.dumps(intent, ensure_ascii=False, sort_keys=True, indent=2)
    preview_uri = "data:image/png;base64," + base64.b64encode(preview_png).decode("ascii")
    sheet_uri = "data:image/svg+xml;base64," + base64.b64encode(stage_contact_sheet.svg).decode("ascii")
    metrics_uri = "data:image/svg+xml;base64," + base64.b64encode(qa_metrics.svg).decode("ascii")

    badges = "".join(
        (
            _badge("QA", f"{qa_status} · {finding_count} findings"),
            _badge("Stages", str(len(frames))),
            _badge("Complexity", complexity_status),
            _badge("Canvas", canvas_label),
        )
    )
    stage_note = (
        "This sheet is linked to stage-image records in the preview bundle."
        if stage_linkage == "bundle-stage-artifacts"
        else "This bundle declares no stage images; the sheet is separate committed review evidence."
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; object-src 'none'">
<title>TracePixel review · {html.escape(asset_class)}</title>
<style>
:root {{ color-scheme: light dark; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: Canvas; color: CanvasText; }}
main {{ width: min(100%, 960px); margin: 0 auto; padding: 20px 16px 48px; }}
header {{ margin-bottom: 18px; }}
h1 {{ margin: 0 0 6px; font-size: clamp(1.55rem, 6vw, 2.2rem); line-height: 1.1; }}
.subtitle {{ margin: 0; opacity: .72; overflow-wrap: anywhere; }}
.badges {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 16px 0 20px; }}
.badge {{ border: 1px solid color-mix(in srgb, CanvasText 22%, transparent); border-radius: 12px; padding: 10px 12px; min-width: 0; }}
.badge-label {{ display: block; font-size: .72rem; opacity: .65; text-transform: uppercase; letter-spacing: .06em; }}
.badge strong {{ display: block; margin-top: 3px; overflow-wrap: anywhere; }}
section {{ margin: 14px 0; border: 1px solid color-mix(in srgb, CanvasText 20%, transparent); border-radius: 14px; padding: 14px; overflow: hidden; }}
h2 {{ margin: 0 0 10px; font-size: 1.05rem; }}
p {{ line-height: 1.45; }}
figure {{ margin: 0; }}
img {{ display: block; max-width: 100%; height: auto; margin: 0 auto; }}
.final-preview {{ image-rendering: pixelated; image-rendering: crisp-edges; }}
figcaption, .note {{ margin-top: 9px; font-size: .82rem; opacity: .7; line-height: 1.4; overflow-wrap: anywhere; }}
pre {{ margin: 0; max-height: 20rem; overflow: auto; padding: 12px; border-radius: 10px; background: color-mix(in srgb, CanvasText 7%, Canvas); font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }}
details summary {{ cursor: pointer; font-weight: 650; }}
details pre {{ margin-top: 10px; }}
.authority {{ display: grid; gap: 6px; font-size: .88rem; }}
.authority code {{ overflow-wrap: anywhere; }}
@media (min-width: 700px) {{ .badges {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }} main {{ padding-top: 28px; }} section {{ padding: 18px; }} }}
</style>
</head>
<body>
<main>
<header>
<h1>TracePixel static review</h1>
<p class="subtitle">{html.escape(asset_class)} · self-contained P6-V3 evidence view</p>
</header>
<div class="badges">{badges}</div>
<section aria-labelledby="final-title">
<h2 id="final-title">Final output</h2>
<figure>
<img class="final-preview" src="{preview_uri}" alt="Nearest-neighbor final pixel-art preview">
<figcaption>Exact P6-V0 preview PNG bytes embedded as a data URI. Gallery layout is presentation-only.</figcaption>
</figure>
</section>
<section aria-labelledby="qa-title">
<h2 id="qa-title">Deterministic QA + Agent metrics</h2>
<figure>
<img src="{metrics_uri}" alt="TracePixel QA and Agent complexity composition">
<figcaption>Deterministic QA remains source evidence. Agent complexity remains observational.</figcaption>
</figure>
</section>
<section aria-labelledby="stages-title">
<h2 id="stages-title">Stage progression evidence</h2>
<figure>
<img src="{sheet_uri}" alt="TracePixel authored-stage contact sheet">
<figcaption>{html.escape(stage_note)}</figcaption>
</figure>
</section>
<section aria-labelledby="intent-title">
<h2 id="intent-title">Task / intent</h2>
<details open>
<summary>{html.escape(asset_class)} · {html.escape(canvas_label)}</summary>
<pre>{html.escape(intent_pretty)}</pre>
</details>
</section>
<section aria-labelledby="authority-title">
<h2 id="authority-title">Authority boundary</h2>
<div class="authority">
<div><strong>Raster truth:</strong> unchanged; this page embeds existing preview evidence.</div>
<div><strong>Deterministic QA:</strong> source evidence from the P6-V0/V2 contract.</div>
<div><strong>Stage + metrics compositions:</strong> presentation-only.</div>
<div><strong>Perceptual/VLM:</strong> not included; unresolved G4 is not crossed.</div>
<div><strong>Human judgment:</strong> final aesthetic judgment is not encoded as machine truth.</div>
<div><strong>Network/runtime:</strong> no external assets, scripts, server, provider call, GPU, or self-hosted runner required.</div>
</div>
</section>
</main>
</body>
</html>
"""
    gallery_html = document.encode("utf-8")

    gallery_manifest: dict[str, object] = {
        "schema": STATIC_HTML_GALLERY_SCHEMA_V1,
        "sources": {
            "bundle_manifest": {
                "schema": PREVIEW_BUNDLE_SCHEMA_V1,
                "size_bytes": len(canonical_bundle_manifest),
                "sha256": sha256(canonical_bundle_manifest).hexdigest(),
            },
            "preview_png": {
                "path": preview_record["path"],
                "size_bytes": len(preview_png),
                "sha256": sha256(preview_png).hexdigest(),
            },
            "intent_summary": {
                "path": intent_record["path"],
                "size_bytes": len(intent_bytes),
                "sha256": sha256(intent_bytes).hexdigest(),
            },
            "stage_contact_sheet": {
                "schema": STAGE_CONTACT_SHEET_SCHEMA_V1,
                "size_bytes": len(stage_contact_sheet.svg),
                "sha256": sha256(stage_contact_sheet.svg).hexdigest(),
                "frame_count": len(frames),
                "linkage": stage_linkage,
            },
            "qa_metrics": {
                "schema": QA_METRICS_COMPOSITION_SCHEMA_V1,
                "size_bytes": len(qa_metrics.svg),
                "sha256": sha256(qa_metrics.svg).hexdigest(),
                "qa_status": qa_summary_typed.get("status"),
                "finding_count": qa_summary_typed.get("finding_count"),
            },
        },
        "gallery": {
            "path": "index.html",
            "media_type": "text/html; charset=utf-8",
            "size_bytes": len(gallery_html),
            "sha256": sha256(gallery_html).hexdigest(),
            "standalone": True,
            "external_dependencies": 0,
            "scripts": 0,
        },
        "authority": {
            "raster_truth": "unchanged",
            "deterministic_qa": "source-evidence",
            "stage_composition": "presentation-only",
            "metrics_composition": "presentation-only",
            "gallery": "presentation-only",
            "perceptual": "not-included",
            "human_judgment": "not-recorded",
        },
    }
    _canonical_json_bytes(gallery_manifest)
    return StaticHtmlGallery(manifest=gallery_manifest, html=gallery_html)


def write_static_html_gallery(gallery: StaticHtmlGallery, output_dir: str | Path) -> None:
    """Materialize one P6-V3 gallery without mixing stale output."""

    if not isinstance(gallery, StaticHtmlGallery):
        _fail("invalid_gallery", "$.gallery", "must be StaticHtmlGallery")
    root = Path(output_dir)
    if root.exists():
        if not root.is_dir():
            _fail("output_not_directory", "$.output_dir", "must be a directory path")
        if any(root.iterdir()):
            _fail(
                "output_not_empty",
                "$.output_dir",
                "refusing to overwrite a non-empty directory",
            )
    else:
        root.mkdir(parents=True)

    root.joinpath("index.html").write_bytes(gallery.html)
    root.joinpath("manifest.json").write_bytes(_canonical_json_bytes(gallery.manifest))
