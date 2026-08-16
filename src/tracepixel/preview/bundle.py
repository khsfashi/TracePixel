from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, cast

from tracepixel.agent import AgentComplexityTelemetryV1, validate_agent_complexity_telemetry
from tracepixel.model import ArtIntentV1, STAGE_SEQUENCE_V1, StageIdV1, validate_art_intent
from tracepixel.qa import MAX_QA_POLICY_RULES_V1, QA_FINDINGS_SCHEMA_V1, QaFindingsV1
from tracepixel.raster import Canvas, export_native_png, export_nearest_preview_png

PREVIEW_BUNDLE_SCHEMA_V1 = "tracepixel.preview-bundle.v1"

StageArtifactKindV1 = Literal["stage-image", "stage-evidence"]
StageArtifactMediaTypeV1 = Literal["image/png", "application/json"]

_STAGE_ORDER = {stage: index for index, stage in enumerate(STAGE_SEQUENCE_V1)}
_QA_CATEGORY_BY_RULE = {
    "structural.non_empty": "structural",
    "structural.no_translucency": "structural",
    "structural.no_edge_contact": "structural",
    "color.palette_membership": "color",
    "color.maximum_colors": "color",
    "color.transparent_rgb_policy": "color",
    "connectivity.single_component": "connectivity",
    "connectivity.no_isolated_pixels": "connectivity",
    "shape.required_symmetry": "shape",
    "tile.contract": "tile",
}
_QA_SEVERITIES = frozenset(("info", "warning", "error"))
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PreviewBundleContractError(ValueError):
    """Stable deterministic rejection for malformed P6-V0 preview-bundle input."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


@dataclass(frozen=True, slots=True)
class PreviewStageArtifact:
    stage: StageIdV1
    kind: StageArtifactKindV1
    name: str
    media_type: StageArtifactMediaTypeV1
    data: bytes


@dataclass(frozen=True, slots=True)
class PreviewBundleFile:
    path: str
    data: bytes


@dataclass(frozen=True, slots=True)
class PreviewBundle:
    manifest: dict[str, object]
    files: tuple[PreviewBundleFile, ...]

    def file_bytes(self, path: str) -> bytes:
        for item in self.files:
            if item.path == path:
                return item.data
        raise KeyError(path)


def _fail(code: str, path: str, message: str) -> None:
    raise PreviewBundleContractError(code, path, message)


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


def _file_record(path: str, media_type: str, data: bytes) -> dict[str, object]:
    return {
        "path": path,
        "media_type": media_type,
        "size_bytes": len(data),
        "sha256": sha256(data).hexdigest(),
    }


def _validate_qa_findings(value: object) -> QaFindingsV1:
    if type(value) is not dict:
        _fail("invalid_qa", "$.deterministic_qa", "must be a JSON object")
    root = cast(dict[object, object], value)
    if not all(type(key) is str for key in root):
        _fail("invalid_qa", "$.deterministic_qa", "object keys must be strings")
    typed = cast(dict[str, object], root)
    if frozenset(typed) != frozenset(("schema", "findings")):
        _fail(
            "invalid_qa",
            "$.deterministic_qa",
            "must contain exactly schema and findings",
        )
    if typed["schema"] != QA_FINDINGS_SCHEMA_V1:
        _fail(
            "unsupported_qa_schema",
            "$.deterministic_qa.schema",
            f"expected {QA_FINDINGS_SCHEMA_V1!r}",
        )
    findings = typed["findings"]
    if type(findings) is not list:
        _fail("invalid_qa", "$.deterministic_qa.findings", "must be an array")
    finding_list = cast(list[object], findings)
    if len(finding_list) > MAX_QA_POLICY_RULES_V1:
        _fail(
            "too_many_qa_findings",
            "$.deterministic_qa.findings",
            f"supports at most {MAX_QA_POLICY_RULES_V1} findings",
        )

    seen: set[str] = set()
    for index, item in enumerate(finding_list):
        path = f"$.deterministic_qa.findings[{index}]"
        if type(item) is not dict:
            _fail("invalid_qa", path, "must be an object")
        finding = cast(dict[object, object], item)
        if not all(type(key) is str for key in finding):
            _fail("invalid_qa", path, "object keys must be strings")
        record = cast(dict[str, object], finding)
        if frozenset(record) != frozenset(("rule", "category", "severity")):
            _fail("invalid_qa", path, "must contain exactly rule, category, and severity")

        rule = record["rule"]
        category = record["category"]
        severity = record["severity"]
        if type(rule) is not str or rule not in _QA_CATEGORY_BY_RULE:
            _fail("invalid_qa_rule", f"{path}.rule", "must be a supported Q5 rule")
        rule_text = cast(str, rule)
        if rule_text in seen:
            _fail("duplicate_qa_rule", f"{path}.rule", f"duplicate rule {rule_text!r}")
        seen.add(rule_text)
        if category != _QA_CATEGORY_BY_RULE[rule_text]:
            _fail("qa_category_mismatch", f"{path}.category", "must match the Q5 rule")
        if type(severity) is not str or severity not in _QA_SEVERITIES:
            _fail(
                "invalid_qa_severity",
                f"{path}.severity",
                "must be info, warning, or error",
            )
    return cast(QaFindingsV1, value)


def _validate_stage_artifact(
    artifact: PreviewStageArtifact,
    index: int,
) -> tuple[int, str]:
    path = f"$.stage_artifacts[{index}]"
    if artifact.stage not in _STAGE_ORDER:
        _fail("invalid_stage", f"{path}.stage", "must be a supported P3 stage")
    if artifact.kind not in ("stage-image", "stage-evidence"):
        _fail(
            "invalid_stage_artifact_kind",
            f"{path}.kind",
            "must be stage-image or stage-evidence",
        )
    if type(artifact.name) is not str or not artifact.name:
        _fail("invalid_stage_artifact_name", f"{path}.name", "must be a non-empty filename")
    if (
        artifact.name in (".", "..")
        or "/" in artifact.name
        or "\\" in artifact.name
        or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for character in artifact.name
        )
    ):
        _fail(
            "invalid_stage_artifact_name",
            f"{path}.name",
            "must be one safe filename using letters, digits, '.', '_', or '-'",
        )
    if artifact.media_type not in ("image/png", "application/json"):
        _fail(
            "unsupported_stage_media_type",
            f"{path}.media_type",
            "must be image/png or application/json",
        )
    if type(artifact.data) is not bytes:
        _fail("invalid_stage_artifact_data", f"{path}.data", "must be bytes")
    if artifact.media_type == "image/png":
        if not artifact.data.startswith(_PNG_SIGNATURE):
            _fail("invalid_stage_png", f"{path}.data", "must start with the PNG signature")
    else:
        try:
            json.loads(artifact.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            _fail("invalid_stage_json", f"{path}.data", f"must be UTF-8 JSON: {exc}")
    return _STAGE_ORDER[artifact.stage], artifact.name


def build_preview_bundle(
    canvas: Canvas,
    *,
    art_intent: ArtIntentV1,
    deterministic_qa: QaFindingsV1,
    complexity_evidence: AgentComplexityTelemetryV1 | None = None,
    stage_artifacts: tuple[PreviewStageArtifact, ...] | list[PreviewStageArtifact] = (),
    preview_scale: int = 8,
) -> PreviewBundle:
    """Build a deterministic P6-V0 review payload without changing raster authority."""

    validate_art_intent(art_intent)
    if (
        art_intent["canvas"]["width"] != canvas.width
        or art_intent["canvas"]["height"] != canvas.height
    ):
        _fail(
            "intent_canvas_mismatch",
            "$.art_intent.canvas",
            "must match the authoritative Canvas dimensions",
        )
    _validate_qa_findings(deterministic_qa)
    if complexity_evidence is not None:
        validate_agent_complexity_telemetry(complexity_evidence)

    native = export_native_png(canvas)
    preview = export_nearest_preview_png(canvas, scale=preview_scale)
    intent_bytes = _canonical_json_bytes(art_intent)
    qa_bytes = _canonical_json_bytes(deterministic_qa)
    complexity_bytes = (
        None if complexity_evidence is None else _canonical_json_bytes(complexity_evidence)
    )

    normalized_stage_artifacts: list[tuple[int, str, PreviewStageArtifact]] = []
    for index, artifact in enumerate(stage_artifacts):
        if not isinstance(artifact, PreviewStageArtifact):
            _fail(
                "invalid_stage_artifact",
                f"$.stage_artifacts[{index}]",
                "must be PreviewStageArtifact",
            )
        order, name = _validate_stage_artifact(artifact, index)
        normalized_stage_artifacts.append((order, name, artifact))
    normalized_stage_artifacts.sort(key=lambda item: (item[0], item[2].kind, item[1]))

    core_files = [
        PreviewBundleFile("image/native.png", native.png),
        PreviewBundleFile(f"image/preview-{preview_scale}x.png", preview.png),
        PreviewBundleFile("evidence/intent.json", intent_bytes),
        PreviewBundleFile("evidence/qa-findings.json", qa_bytes),
    ]
    if complexity_bytes is not None:
        core_files.append(
            PreviewBundleFile("evidence/agent-complexity.json", complexity_bytes)
        )

    stage_files: list[PreviewBundleFile] = []
    stage_records: list[dict[str, object]] = []
    seen_stage_paths: set[str] = set()
    for _, _, artifact in normalized_stage_artifacts:
        relative_path = f"stages/{artifact.stage}/{artifact.name}"
        if relative_path in seen_stage_paths:
            _fail(
                "duplicate_stage_artifact_path",
                "$.stage_artifacts",
                f"duplicate bundle path {relative_path!r}",
            )
        seen_stage_paths.add(relative_path)
        stage_files.append(PreviewBundleFile(relative_path, artifact.data))
        record = _file_record(relative_path, artifact.media_type, artifact.data)
        record["stage"] = artifact.stage
        record["kind"] = artifact.kind
        stage_records.append(record)

    native_record = _file_record("image/native.png", "image/png", native.png)
    native_record["export"] = native.metadata.as_dict()
    preview_path = f"image/preview-{preview_scale}x.png"
    preview_record = _file_record(preview_path, "image/png", preview.png)
    preview_record["export"] = preview.metadata.as_dict()

    manifest: dict[str, object] = {
        "schema": PREVIEW_BUNDLE_SCHEMA_V1,
        "source": {
            "width": canvas.width,
            "height": canvas.height,
            "pixel_format": "RGBA8",
            "authoritative_rgba_sha256": native.metadata.authoritative_rgba_sha256,
        },
        "native_png": native_record,
        "preview_png": preview_record,
        "intent_summary": _file_record(
            "evidence/intent.json",
            "application/json",
            intent_bytes,
        ),
        "deterministic_qa": _file_record(
            "evidence/qa-findings.json",
            "application/json",
            qa_bytes,
        ),
        "complexity_evidence": (
            None
            if complexity_bytes is None
            else _file_record(
                "evidence/agent-complexity.json",
                "application/json",
                complexity_bytes,
            )
        ),
        "stage_artifacts": stage_records,
        "authority": {
            "raster": "authoritative-rgba-derived",
            "deterministic_qa": "deterministic",
            "intent": "authoring-input",
            "complexity": "observational",
            "perceptual": "not-included",
        },
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    files = (
        PreviewBundleFile("manifest.json", manifest_bytes),
        *core_files,
        *stage_files,
    )
    return PreviewBundle(manifest=manifest, files=tuple(files))


def write_preview_bundle(bundle: PreviewBundle, output_dir: str | Path) -> None:
    """Write one complete bundle, refusing to mix with stale pre-existing files."""

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
