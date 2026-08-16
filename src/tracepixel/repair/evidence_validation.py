from __future__ import annotations

import base64
import html
import json
from hashlib import sha256
from pathlib import Path
from typing import cast

from tracepixel.raster import Canvas, export_native_png, export_nearest_preview_png

from .evidence import (
    REPAIR_EVIDENCE_SCHEMA_V1,
    RepairEvidenceArtifactV1,
    RepairEvidenceBundle,
    RepairEvidenceFile,
    RepairEvidenceV1,
)
from .execution import RepairExecutionV1, RepairQaEvaluator
from .execution_validation import (
    RepairExecutionValidationError,
    execute_repair_plan,
    validate_repair_execution,
)

_ROOT_FIELDS = frozenset(
    (
        "schema",
        "execution",
        "preview_scale",
        "before_native_png",
        "before_preview_png",
        "after_native_png",
        "after_preview_png",
        "qa_evidence",
        "gallery_html",
        "authority",
    )
)
_ARTIFACT_FIELDS = frozenset(
    ("path", "media_type", "size_bytes", "sha256", "authoritative_rgba_sha256")
)
_AUTHORITY_FIELDS = frozenset(("raster", "deterministic_qa", "human", "perceptual"))
_HEX_DIGITS = frozenset("0123456789abcdef")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class RepairEvidenceValidationError(ValueError):
    """Deterministic P7-F4 rejection with stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise RepairEvidenceValidationError(code, path, message)


def _require_exact_object(
    value: object,
    path: str,
    fields: frozenset[str],
) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    obj = cast(dict[object, object], value)
    if not all(type(key) is str for key in obj):
        _fail("invalid_fields", path, "object keys must be strings")
    typed = cast(dict[str, object], obj)
    actual = frozenset(typed)
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail("invalid_fields", path, "; ".join(parts))
    return typed


def _require_digest(value: object, path: str) -> str:
    if (
        type(value) is not str
        or len(cast(str, value)) != 64
        or any(character not in _HEX_DIGITS for character in cast(str, value))
    ):
        _fail("invalid_digest", path, "must be 64 lowercase hexadecimal characters")
    return cast(str, value)


def _validated_execution(value: object) -> RepairExecutionV1:
    try:
        return validate_repair_execution(value)
    except RepairExecutionValidationError as exc:
        path = "$.execution" if exc.path == "$" else f"$.execution{exc.path[1:]}"
        _fail(
            "invalid_execution",
            path,
            f"repair execution validation failed with {exc.code}: {exc.message}",
        )


def _validate_artifact(
    value: object,
    path: str,
    *,
    expected_path: str,
    expected_media_type: str,
    authoritative_rgba_sha256: str | None,
) -> RepairEvidenceArtifactV1:
    record = _require_exact_object(value, path, _ARTIFACT_FIELDS)
    if record["path"] != expected_path:
        _fail("artifact_path_mismatch", f"{path}.path", f"expected {expected_path!r}")
    if record["media_type"] != expected_media_type:
        _fail(
            "artifact_media_type_mismatch",
            f"{path}.media_type",
            f"expected {expected_media_type!r}",
        )
    size = record["size_bytes"]
    if type(size) is not int or cast(int, size) <= 0:
        _fail("invalid_artifact_size", f"{path}.size_bytes", "must be a positive integer")
    _require_digest(record["sha256"], f"{path}.sha256")
    if record["authoritative_rgba_sha256"] != authoritative_rgba_sha256:
        _fail(
            "artifact_raster_identity_mismatch",
            f"{path}.authoritative_rgba_sha256",
            "must match the linked F3 authoritative RGBA digest",
        )
    return cast(RepairEvidenceArtifactV1, value)


def validate_repair_evidence(value: object) -> RepairEvidenceV1:
    """Validate the closed F4 visual-evidence manifest and F3 identity linkage."""

    root = _require_exact_object(value, "$", _ROOT_FIELDS)
    if root["schema"] != REPAIR_EVIDENCE_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"expected {REPAIR_EVIDENCE_SCHEMA_V1!r}",
        )

    execution = _validated_execution(root["execution"])
    scale = root["preview_scale"]
    if type(scale) is not int or cast(int, scale) < 2:
        _fail("invalid_preview_scale", "$.preview_scale", "must be an exact integer >= 2")
    preview_scale = cast(int, scale)

    source_digest = execution["source_rgba_sha256"]
    result_digest = execution["result_rgba_sha256"]
    _validate_artifact(
        root["before_native_png"],
        "$.before_native_png",
        expected_path="before/native.png",
        expected_media_type="image/png",
        authoritative_rgba_sha256=source_digest,
    )
    _validate_artifact(
        root["before_preview_png"],
        "$.before_preview_png",
        expected_path=f"before/preview-{preview_scale}x.png",
        expected_media_type="image/png",
        authoritative_rgba_sha256=source_digest,
    )
    _validate_artifact(
        root["after_native_png"],
        "$.after_native_png",
        expected_path="after/native.png",
        expected_media_type="image/png",
        authoritative_rgba_sha256=result_digest,
    )
    _validate_artifact(
        root["after_preview_png"],
        "$.after_preview_png",
        expected_path=f"after/preview-{preview_scale}x.png",
        expected_media_type="image/png",
        authoritative_rgba_sha256=result_digest,
    )
    _validate_artifact(
        root["qa_evidence"],
        "$.qa_evidence",
        expected_path="evidence/qa-findings.json",
        expected_media_type="application/json",
        authoritative_rgba_sha256=None,
    )
    _validate_artifact(
        root["gallery_html"],
        "$.gallery_html",
        expected_path="index.html",
        expected_media_type="text/html",
        authoritative_rgba_sha256=None,
    )

    authority = _require_exact_object(root["authority"], "$.authority", _AUTHORITY_FIELDS)
    expected_authority = {
        "raster": "authoritative-rgba-derived",
        "deterministic_qa": "deterministic",
        "human": "not-recorded",
        "perceptual": "not-included",
    }
    if authority != expected_authority:
        _fail(
            "invalid_authority_boundary",
            "$.authority",
            "F4 must retain deterministic raster/QA authority without human or perceptual judgment",
        )
    return cast(RepairEvidenceV1, value)


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


def _artifact_record(
    path: str,
    media_type: str,
    data: bytes,
    *,
    authoritative_rgba_sha256: str | None,
) -> RepairEvidenceArtifactV1:
    return {
        "path": path,
        "media_type": cast(object, media_type),
        "size_bytes": len(data),
        "sha256": sha256(data).hexdigest(),
        "authoritative_rgba_sha256": authoritative_rgba_sha256,
    }  # type: ignore[return-value]


def _render_gallery(
    execution: RepairExecutionV1,
    *,
    before_preview: bytes,
    after_preview: bytes,
    preview_scale: int,
) -> bytes:
    target = execution["plan"]["localization"]["intake"]["target"]
    asset_id = html.escape(target["asset_id"])
    task_id = html.escape(target["task_id"])
    applied_stages = [
        item["target_stage"]
        for item in execution["executions"]
        if item["status"] == "applied" and item["target_stage"] is not None
    ]
    stages = html.escape(", ".join(applied_stages) if applied_stages else "none")
    qa_count = len(execution["qa"]["findings"])
    qa_status = "no findings" if qa_count == 0 else f"{qa_count} finding(s)"
    qa_pretty = html.escape(
        json.dumps(execution["qa"], ensure_ascii=False, indent=2, sort_keys=True)
    )
    before_uri = base64.b64encode(before_preview).decode("ascii")
    after_uri = base64.b64encode(after_preview).decode("ascii")

    document = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<meta http-equiv=\"Content-Security-Policy\" "
        "content=\"default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
        "base-uri 'none'; object-src 'none'; form-action 'none'\">"
        "<title>TracePixel P7-F4 Repair Evidence</title>"
        "<style>"
        "*{box-sizing:border-box}body{margin:0;background:#101216;color:#f4f6f8;"
        "font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}"
        "main{max-width:980px;margin:0 auto;padding:20px}h1{font-size:clamp(1.45rem,5vw,2.2rem);"
        "margin:.2rem 0 .5rem}p{line-height:1.55}.muted{color:#aeb7c2}"
        ".meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;"
        "margin:18px 0}.badge,.panel{background:#191d24;border:1px solid #303744;border-radius:12px;"
        "padding:12px;min-width:0}.label{display:block;color:#9da8b5;font-size:.78rem;"
        "text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}"
        ".value{display:block;font-weight:700;overflow-wrap:anywhere;word-break:break-word}"
        ".compare{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}"
        ".image-wrap{display:grid;place-items:center;overflow:auto;min-height:220px;background:#0b0d11;"
        "border-radius:10px;padding:12px}.image-wrap img{display:block;max-width:100%;height:auto;"
        "image-rendering:pixelated;image-rendering:crisp-edges}h2{font-size:1.1rem;margin:.2rem 0 .8rem}"
        "details{margin-top:16px}.qa{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;"
        "font-size:.8rem;line-height:1.45;background:#0b0d11;padding:12px;border-radius:10px;overflow:auto}"
        ".boundary{margin-top:16px;border-left:4px solid #8a94a3;padding:10px 12px;background:#171a20;"
        "overflow-wrap:anywhere}@media(max-width:640px){main{padding:14px}.compare{grid-template-columns:1fr}"
        ".image-wrap{min-height:180px}}"
        "</style></head><body><main>"
        "<h1>Before / After Repair Evidence</h1>"
        f"<p class=\"muted\">TracePixel P7-F4 · nearest-neighbor preview {preview_scale}×</p>"
        "<section class=\"meta\">"
        f"<div class=\"badge\"><span class=\"label\">Asset</span><span class=\"value\">{asset_id}</span></div>"
        f"<div class=\"badge\"><span class=\"label\">Task</span><span class=\"value\">{task_id}</span></div>"
        f"<div class=\"badge\"><span class=\"label\">Changed pixels</span><span class=\"value\">{execution['observed_changed_pixel_count']}</span></div>"
        f"<div class=\"badge\"><span class=\"label\">Applied edits</span><span class=\"value\">{execution['applied_pixel_edit_count']}</span></div>"
        f"<div class=\"badge\"><span class=\"label\">Affected stages</span><span class=\"value\">{stages}</span></div>"
        f"<div class=\"badge\"><span class=\"label\">Deterministic QA</span><span class=\"value\">{html.escape(qa_status)}</span></div>"
        "</section><section class=\"compare\">"
        "<article class=\"panel\"><h2>Before</h2><div class=\"image-wrap\">"
        f"<img alt=\"Before repair preview\" src=\"data:image/png;base64,{before_uri}\">"
        "</div></article>"
        "<article class=\"panel\"><h2>After</h2><div class=\"image-wrap\">"
        f"<img alt=\"After repair preview\" src=\"data:image/png;base64,{after_uri}\">"
        "</div></article></section>"
        "<details class=\"panel\"><summary>Deterministic QA evidence</summary>"
        f"<pre class=\"qa\">{qa_pretty}</pre></details>"
        "<p class=\"boundary\"><strong>Authority boundary:</strong> deterministic QA and visual evidence "
        "do not constitute human or perceptual acceptance. Human feedback remains P7-F5.</p>"
        "</main></body></html>"
    )
    return document.encode("utf-8")


def _verify_bundle_files(bundle: RepairEvidenceBundle) -> None:
    manifest_bytes = _canonical_json_bytes(bundle.manifest)
    try:
        materialized_manifest = bundle.file_bytes("manifest.json")
    except KeyError:
        _fail("missing_manifest", "$.files", "bundle must contain manifest.json")
    if materialized_manifest != manifest_bytes:
        _fail("manifest_mismatch", "$.files.manifest.json", "must equal canonical manifest bytes")

    artifact_keys = (
        "before_native_png",
        "before_preview_png",
        "after_native_png",
        "after_preview_png",
        "qa_evidence",
        "gallery_html",
    )
    for key in artifact_keys:
        record = bundle.manifest[key]
        try:
            data = bundle.file_bytes(record["path"])
        except KeyError:
            _fail("missing_artifact", f"$.{key}", f"bundle is missing {record['path']!r}")
        if len(data) != record["size_bytes"]:
            _fail("artifact_size_mismatch", f"$.{key}", "materialized size does not match manifest")
        if sha256(data).hexdigest() != record["sha256"]:
            _fail("artifact_digest_mismatch", f"$.{key}", "materialized SHA-256 does not match manifest")

    if not bundle.file_bytes(bundle.manifest["before_native_png"]["path"]).startswith(_PNG_SIGNATURE):
        _fail("invalid_png", "$.before_native_png", "materialized artifact must be PNG")
    if not bundle.file_bytes(bundle.manifest["before_preview_png"]["path"]).startswith(_PNG_SIGNATURE):
        _fail("invalid_png", "$.before_preview_png", "materialized artifact must be PNG")
    if not bundle.file_bytes(bundle.manifest["after_native_png"]["path"]).startswith(_PNG_SIGNATURE):
        _fail("invalid_png", "$.after_native_png", "materialized artifact must be PNG")
    if not bundle.file_bytes(bundle.manifest["after_preview_png"]["path"]).startswith(_PNG_SIGNATURE):
        _fail("invalid_png", "$.after_preview_png", "materialized artifact must be PNG")

    qa_bytes = _canonical_json_bytes(bundle.manifest["execution"]["qa"])
    if bundle.file_bytes(bundle.manifest["qa_evidence"]["path"]) != qa_bytes:
        _fail("qa_evidence_mismatch", "$.qa_evidence", "must materialize the exact F3 deterministic QA")

    gallery = bundle.file_bytes(bundle.manifest["gallery_html"]["path"])
    if b"<script" in gallery.lower():
        _fail("unsafe_gallery", "$.gallery_html", "must not contain JavaScript")
    if b"http://" in gallery.lower() or b"https://" in gallery.lower():
        _fail("unsafe_gallery", "$.gallery_html", "must not reference external network resources")


def build_repair_evidence(
    plan: object,
    *,
    canvas: Canvas,
    qa_evaluator: RepairQaEvaluator,
    preview_scale: int = 8,
) -> RepairEvidenceBundle:
    """Render exact before evidence, execute F3 once, then render exact after/QA evidence.

    The caller-owned Canvas is mutated in place by the existing F3 executor. F4 retains only the
    encoded artifacts required for review; it does not retain a second authoritative raw raster.
    """

    if type(preview_scale) is not int or preview_scale < 2:
        _fail("invalid_preview_scale", "$.preview_scale", "must be an exact integer >= 2")

    before_native = export_native_png(canvas)
    before_preview = export_nearest_preview_png(canvas, scale=preview_scale)
    execution = execute_repair_plan(plan, canvas=canvas, qa_evaluator=qa_evaluator)
    after_native = export_native_png(canvas)
    after_preview = export_nearest_preview_png(canvas, scale=preview_scale)

    if before_native.metadata.authoritative_rgba_sha256 != execution["source_rgba_sha256"]:
        _fail(
            "source_identity_mismatch",
            "$.execution.source_rgba_sha256",
            "F3 source digest must equal the pre-execution authoritative raster",
        )
    if before_preview.metadata.authoritative_rgba_sha256 != execution["source_rgba_sha256"]:
        _fail(
            "source_identity_mismatch",
            "$.before_preview_png",
            "before preview must derive from the same F3 source raster",
        )
    if after_native.metadata.authoritative_rgba_sha256 != execution["result_rgba_sha256"]:
        _fail(
            "result_identity_mismatch",
            "$.execution.result_rgba_sha256",
            "F3 result digest must equal the post-execution authoritative raster",
        )
    if after_preview.metadata.authoritative_rgba_sha256 != execution["result_rgba_sha256"]:
        _fail(
            "result_identity_mismatch",
            "$.after_preview_png",
            "after preview must derive from the same F3 result raster",
        )

    qa_bytes = _canonical_json_bytes(execution["qa"])
    gallery_bytes = _render_gallery(
        execution,
        before_preview=before_preview.png,
        after_preview=after_preview.png,
        preview_scale=preview_scale,
    )

    manifest: RepairEvidenceV1 = {
        "schema": REPAIR_EVIDENCE_SCHEMA_V1,
        "execution": execution,
        "preview_scale": preview_scale,
        "before_native_png": _artifact_record(
            "before/native.png",
            "image/png",
            before_native.png,
            authoritative_rgba_sha256=execution["source_rgba_sha256"],
        ),
        "before_preview_png": _artifact_record(
            f"before/preview-{preview_scale}x.png",
            "image/png",
            before_preview.png,
            authoritative_rgba_sha256=execution["source_rgba_sha256"],
        ),
        "after_native_png": _artifact_record(
            "after/native.png",
            "image/png",
            after_native.png,
            authoritative_rgba_sha256=execution["result_rgba_sha256"],
        ),
        "after_preview_png": _artifact_record(
            f"after/preview-{preview_scale}x.png",
            "image/png",
            after_preview.png,
            authoritative_rgba_sha256=execution["result_rgba_sha256"],
        ),
        "qa_evidence": _artifact_record(
            "evidence/qa-findings.json",
            "application/json",
            qa_bytes,
            authoritative_rgba_sha256=None,
        ),
        "gallery_html": _artifact_record(
            "index.html",
            "text/html",
            gallery_bytes,
            authoritative_rgba_sha256=None,
        ),
        "authority": {
            "raster": "authoritative-rgba-derived",
            "deterministic_qa": "deterministic",
            "human": "not-recorded",
            "perceptual": "not-included",
        },
    }
    validate_repair_evidence(manifest)
    manifest_bytes = _canonical_json_bytes(manifest)
    bundle = RepairEvidenceBundle(
        manifest=manifest,
        files=(
            RepairEvidenceFile("manifest.json", manifest_bytes),
            RepairEvidenceFile("before/native.png", before_native.png),
            RepairEvidenceFile(f"before/preview-{preview_scale}x.png", before_preview.png),
            RepairEvidenceFile("after/native.png", after_native.png),
            RepairEvidenceFile(f"after/preview-{preview_scale}x.png", after_preview.png),
            RepairEvidenceFile("evidence/qa-findings.json", qa_bytes),
            RepairEvidenceFile("index.html", gallery_bytes),
        ),
    )
    _verify_bundle_files(bundle)
    return bundle


def write_repair_evidence_bundle(
    bundle: RepairEvidenceBundle,
    output_dir: str | Path,
) -> None:
    """Materialize one complete F4 bundle, refusing to mix with stale files."""

    if not isinstance(bundle, RepairEvidenceBundle):
        _fail("invalid_bundle", "$.bundle", "must be RepairEvidenceBundle")
    validate_repair_evidence(bundle.manifest)
    _verify_bundle_files(bundle)

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

    for item in bundle.files:
        target = root.joinpath(*item.path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item.data)
