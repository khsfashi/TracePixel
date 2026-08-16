from __future__ import annotations

import base64
import html
import json
import struct
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

from tracepixel.agent import AgentComplexityTelemetryV1, validate_agent_complexity_telemetry
from tracepixel.qa import QA_FINDINGS_SCHEMA_V1, QaFindingsV1

from .bundle import PREVIEW_BUNDLE_SCHEMA_V1, PreviewBundle, _validate_qa_findings

QA_METRICS_COMPOSITION_SCHEMA_V1 = "tracepixel.qa-metrics-composition.v1"

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PADDING = 16
_GAP = 16
_PANEL_WIDTH = 420
_LINE_HEIGHT = 20
_TITLE_HEIGHT = 28
_SECTION_GAP = 18


class QaMetricsCompositionContractError(ValueError):
    """Stable deterministic rejection for malformed P6-V2 composition input."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


@dataclass(frozen=True, slots=True)
class QaMetricsComposition:
    manifest: dict[str, object]
    svg: bytes


def _fail(code: str, path: str, message: str) -> None:
    raise QaMetricsCompositionContractError(code, path, message)


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


def _manifest_record(manifest: dict[str, object], key: str, *, optional: bool = False) -> dict[str, object] | None:
    value = manifest.get(key)
    if value is None and optional:
        return None
    if type(value) is not dict:
        _fail("invalid_bundle_manifest", f"$.bundle.manifest.{key}", "must be a file record object")
    record = cast(dict[object, object], value)
    if not all(type(item) is str for item in record):
        _fail("invalid_bundle_manifest", f"$.bundle.manifest.{key}", "record keys must be strings")
    typed = cast(dict[str, object], record)
    for field in ("path", "media_type", "size_bytes", "sha256"):
        if field not in typed:
            _fail(
                "invalid_bundle_manifest",
                f"$.bundle.manifest.{key}",
                f"missing required field {field!r}",
            )
    return typed


def _bundle_file(bundle: PreviewBundle, record: dict[str, object], path: str, media_type: str) -> bytes:
    recorded_path = record["path"]
    if type(recorded_path) is not str or not recorded_path:
        _fail("invalid_bundle_manifest", f"{path}.path", "must be a non-empty string")
    if record["media_type"] != media_type:
        _fail("unexpected_media_type", f"{path}.media_type", f"expected {media_type!r}")
    expected_size = record["size_bytes"]
    if type(expected_size) is not int or expected_size < 0:
        _fail("invalid_bundle_manifest", f"{path}.size_bytes", "must be a non-negative integer")
    expected_sha = record["sha256"]
    if type(expected_sha) is not str or len(expected_sha) != 64:
        _fail("invalid_bundle_manifest", f"{path}.sha256", "must be a SHA-256 hex digest")
    try:
        data = bundle.file_bytes(recorded_path)
    except KeyError:
        _fail("missing_bundle_file", path, f"bundle is missing {recorded_path!r}")
    if len(data) != expected_size:
        _fail("bundle_size_mismatch", path, f"size does not match manifest for {recorded_path!r}")
    if sha256(data).hexdigest() != expected_sha:
        _fail("bundle_digest_mismatch", path, f"SHA-256 does not match manifest for {recorded_path!r}")
    return data


def _png_dimensions(data: bytes, path: str) -> tuple[int, int]:
    if len(data) < 33 or not data.startswith(_PNG_SIGNATURE):
        _fail("invalid_preview_png", path, "must be a complete PNG beginning with the PNG signature")
    ihdr_length = struct.unpack(">I", data[8:12])[0]
    if ihdr_length != 13 or data[12:16] != b"IHDR":
        _fail("invalid_preview_png", path, "must begin with a standard 13-byte IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    if width < 1 or height < 1:
        _fail("invalid_preview_png", path, "PNG dimensions must be positive")
    return width, height


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


def _text(value: object) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _svg_text(x: int, y: int, value: str, *, size: int = 14, weight: int = 400) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
        f'font-size="{size}" font-weight="{weight}" fill="#111">{html.escape(value)}</text>'
    )


def build_qa_metrics_composition(bundle: PreviewBundle) -> QaMetricsComposition:
    """Compose P6-V0 image, deterministic QA, and observational Agent metrics into one SVG."""

    if not isinstance(bundle, PreviewBundle):
        _fail("invalid_bundle", "$.bundle", "must be PreviewBundle")
    manifest = bundle.manifest
    if type(manifest) is not dict or manifest.get("schema") != PREVIEW_BUNDLE_SCHEMA_V1:
        _fail(
            "unsupported_bundle_schema",
            "$.bundle.manifest.schema",
            f"expected {PREVIEW_BUNDLE_SCHEMA_V1!r}",
        )

    preview_record = _manifest_record(manifest, "preview_png")
    qa_record = _manifest_record(manifest, "deterministic_qa")
    complexity_record = _manifest_record(manifest, "complexity_evidence", optional=True)
    assert preview_record is not None
    assert qa_record is not None

    preview_png = _bundle_file(bundle, preview_record, "$.bundle.manifest.preview_png", "image/png")
    preview_width, preview_height = _png_dimensions(preview_png, "$.bundle.preview_png")

    qa_data = _bundle_file(
        bundle,
        qa_record,
        "$.bundle.manifest.deterministic_qa",
        "application/json",
    )
    qa_json = _json_object(qa_data, "$.bundle.deterministic_qa")
    if qa_json.get("schema") != QA_FINDINGS_SCHEMA_V1:
        _fail(
            "unsupported_qa_schema",
            "$.bundle.deterministic_qa.schema",
            f"expected {QA_FINDINGS_SCHEMA_V1!r}",
        )
    qa_findings = _validate_qa_findings(qa_json)

    complexity: AgentComplexityTelemetryV1 | None = None
    if complexity_record is not None:
        complexity_data = _bundle_file(
            bundle,
            complexity_record,
            "$.bundle.manifest.complexity_evidence",
            "application/json",
        )
        complexity_json = _json_object(complexity_data, "$.bundle.complexity_evidence")
        complexity = validate_agent_complexity_telemetry(complexity_json)

    findings = cast(list[dict[str, object]], qa_findings["findings"])
    qa_lines = [f"status: {'PASS' if not findings else 'FINDINGS'}", f"finding_count: {len(findings)}"]
    qa_lines.extend(
        f"{item['severity']} | {item['category']} | {item['rule']}" for item in findings
    )

    metric_fields = (
        "input_tokens",
        "output_tokens",
        "tool_calls",
        "operation_calls",
        "exposed_concept_count",
        "visual_observation_calls",
        "iterations",
        "revisions",
        "changed_pixels",
        "wall_time_ns",
        "api_cost_usd_micros",
        "human_interventions",
        "failure_category",
    )
    metric_lines = (
        ["not available"]
        if complexity is None
        else [f"{field}: {_text(complexity[field])}" for field in metric_fields]
    )

    image_x = _PADDING
    image_y = _PADDING + _TITLE_HEIGHT
    panel_x = image_x + preview_width + _GAP
    content_line_count = len(qa_lines) + len(metric_lines) + 8
    content_height = _PADDING + _TITLE_HEIGHT + content_line_count * _LINE_HEIGHT + 3 * _SECTION_GAP
    height = max(image_y + preview_height + _PADDING, content_height)
    width = panel_x + _PANEL_WIDTH + _PADDING

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
        _svg_text(_PADDING, _PADDING + 18, "TracePixel P6-V2 QA / metrics composition", size=16, weight=700),
        f'<image x="{image_x}" y="{image_y}" width="{preview_width}" height="{preview_height}" '
        f'href="data:image/png;base64,{base64.b64encode(preview_png).decode("ascii")}"/>',
        _svg_text(image_x, image_y + preview_height + 18, "preview PNG · exact source bytes · scaling none", size=11),
    ]

    y = image_y
    lines.append(_svg_text(panel_x, y + 16, "Deterministic QA", size=15, weight=700))
    y += _TITLE_HEIGHT
    for item in qa_lines:
        lines.append(_svg_text(panel_x, y + 14, item))
        y += _LINE_HEIGHT

    y += _SECTION_GAP
    lines.append(_svg_text(panel_x, y + 16, "Agent complexity · observational", size=15, weight=700))
    y += _TITLE_HEIGHT
    for item in metric_lines:
        lines.append(_svg_text(panel_x, y + 14, item))
        y += _LINE_HEIGHT

    y += _SECTION_GAP
    lines.append(_svg_text(panel_x, y + 16, "Authority boundary", size=15, weight=700))
    y += _TITLE_HEIGHT
    for item in (
        "raster: unchanged authoritative RGBA-derived evidence",
        "deterministic QA: source evidence; not presentation-derived",
        "complexity: observational only",
        "perceptual/VLM: not included",
        "human judgment: not included",
    ):
        lines.append(_svg_text(panel_x, y + 14, item, size=12))
        y += _LINE_HEIGHT

    lines.append("</svg>")
    svg = "\n".join(lines).encode("utf-8")

    composition_manifest: dict[str, object] = {
        "schema": QA_METRICS_COMPOSITION_SCHEMA_V1,
        "source_bundle_schema": PREVIEW_BUNDLE_SCHEMA_V1,
        "image": {
            "path": preview_record["path"],
            "size_bytes": len(preview_png),
            "sha256": sha256(preview_png).hexdigest(),
            "width": preview_width,
            "height": preview_height,
            "source_image_scaling": "none",
        },
        "deterministic_qa": {
            "path": qa_record["path"],
            "sha256": sha256(qa_data).hexdigest(),
            "status": "pass" if not findings else "findings",
            "finding_count": len(findings),
            "findings": findings,
        },
        "agent_complexity": (
            None
            if complexity is None
            else {
                "path": cast(dict[str, object], complexity_record)["path"],
                "sha256": sha256(complexity_data).hexdigest(),
                "telemetry": complexity,
            }
        ),
        "composition": {
            "media_type": "image/svg+xml",
            "width": width,
            "height": height,
            "size_bytes": len(svg),
            "sha256": sha256(svg).hexdigest(),
        },
        "authority": {
            "raster_truth": "unchanged",
            "deterministic_qa": "source-evidence",
            "complexity": "observational",
            "perceptual": "not-included",
            "human_judgment": "not-included",
        },
    }
    _canonical_json_bytes(composition_manifest)
    return QaMetricsComposition(manifest=composition_manifest, svg=svg)


def write_qa_metrics_composition(
    composition: QaMetricsComposition,
    output_dir: str | Path,
) -> None:
    """Write one P6-V2 composition without mixing with stale output."""

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

    root.joinpath("qa-metrics.svg").write_bytes(composition.svg)
    root.joinpath("manifest.json").write_bytes(_canonical_json_bytes(composition.manifest))
