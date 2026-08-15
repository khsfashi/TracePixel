from __future__ import annotations

import hashlib
import json
from typing import Literal, TypedDict, cast

from tracepixel.raster import Canvas, PngExportMetadata, export_nearest_preview_png

from .execution import PixelProgramCanvasMismatchError, apply_pixel_program
from .pixel_ir import PixelProgramV1
from .serialization import serialize_pixel_program
from .stage_plan import (
    STAGE_SEQUENCE_V1,
    StageIdV1,
    StageInputIdV1,
    StageStatusV1,
    _fail,
    _require_exact_array,
    _require_exact_object,
    _validate_skip_reason,
)

STAGE_PIPELINE_EVIDENCE_SCHEMA_V1 = "tracepixel.stage-pipeline-evidence.v1"

_EVIDENCE_FIELDS = frozenset((
    "schema",
    "art_intent_sha256",
    "stage_plan_sha256",
    "canvas",
    "stages",
    "final_rgba_sha256",
))
_EVIDENCE_CANVAS_FIELDS = frozenset(("width", "height"))
_TRANSITION_FIELDS = frozenset((
    "stage",
    "input_stage",
    "status",
    "skip_reason",
    "input_rgba_sha256",
    "output_rgba_sha256",
    "program",
    "program_sha256",
    "operation_count",
    "edit_count",
    "touched_bounds",
    "preview",
))
_PREVIEW_FIELDS = frozenset(("kind", "scale", "width", "height", "png_sha256"))
_SHA256_CHARS = frozenset("0123456789abcdef")


class TouchedBoundsV1(TypedDict):
    x: int
    y: int
    width: int
    height: int


class StagePreviewEvidenceV1(TypedDict):
    kind: Literal["nearest-preview"]
    scale: int
    width: int
    height: int
    png_sha256: str


class StageTransitionEvidenceV1(TypedDict):
    stage: StageIdV1
    input_stage: StageInputIdV1
    status: StageStatusV1
    skip_reason: str | None
    input_rgba_sha256: str
    output_rgba_sha256: str
    program: PixelProgramV1 | None
    program_sha256: str | None
    operation_count: int
    edit_count: int
    touched_bounds: TouchedBoundsV1 | None
    preview: StagePreviewEvidenceV1 | None


class StagePipelineEvidenceV1(TypedDict):
    schema: Literal["tracepixel.stage-pipeline-evidence.v1"]
    art_intent_sha256: str
    stage_plan_sha256: str
    canvas: dict[str, int]
    stages: list[StageTransitionEvidenceV1]
    final_rgba_sha256: str


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canvas_sha256(canvas: Canvas) -> str:
    """Hash authoritative bytes through the package-internal view without a full copy."""

    return hashlib.sha256(canvas._rgba_view()).hexdigest()


def _validate_sha256(value: object, path: str) -> str:
    if type(value) is not str:
        _fail("invalid_evidence", path, "must be a lowercase SHA-256 string")
    digest = cast(str, value)
    if len(digest) != 64 or any(character not in _SHA256_CHARS for character in digest):
        _fail(
            "invalid_evidence",
            path,
            "must contain exactly 64 lowercase hexadecimal characters",
        )
    return digest


def _program_stats(program: PixelProgramV1) -> tuple[int, int, TouchedBoundsV1 | None]:
    operation_count = len(program["operations"])
    edit_count = 0
    min_x: int | None = None
    min_y: int | None = None
    max_x: int | None = None
    max_y: int | None = None

    for operation in program["operations"]:
        for pixel in operation["pixels"]:
            edit_count += 1
            x, y = pixel[0], pixel[1]
            min_x = x if min_x is None else min(min_x, x)
            min_y = y if min_y is None else min(min_y, y)
            max_x = x if max_x is None else max(max_x, x)
            max_y = y if max_y is None else max(max_y, y)

    if min_x is None or min_y is None or max_x is None or max_y is None:
        return operation_count, edit_count, None
    return operation_count, edit_count, {
        "x": min_x,
        "y": min_y,
        "width": max_x - min_x + 1,
        "height": max_y - min_y + 1,
    }


def _preview_evidence(metadata: PngExportMetadata) -> StagePreviewEvidenceV1:
    return {
        "kind": "nearest-preview",
        "scale": metadata.scale,
        "width": metadata.width,
        "height": metadata.height,
        "png_sha256": metadata.png_sha256,
    }


def serialize_stage_pipeline_evidence(evidence: StagePipelineEvidenceV1) -> bytes:
    """Return canonical UTF-8 JSON evidence bytes suitable for hashing/storage."""

    return _canonical_json_bytes(evidence)


def replay_stage_pipeline_evidence(evidence: object) -> Canvas:
    """Replay and integrity-check one recorded S1-S6 transition chain provider-free."""

    root = _require_exact_object(evidence, "$", _EVIDENCE_FIELDS)
    if root["schema"] != STAGE_PIPELINE_EVIDENCE_SCHEMA_V1:
        _fail(
            "unsupported_evidence_schema",
            "$.schema",
            f"expected {STAGE_PIPELINE_EVIDENCE_SCHEMA_V1!r}",
        )

    _validate_sha256(root["art_intent_sha256"], "$.art_intent_sha256")
    _validate_sha256(root["stage_plan_sha256"], "$.stage_plan_sha256")
    final_digest = _validate_sha256(root["final_rgba_sha256"], "$.final_rgba_sha256")

    canvas_document = _require_exact_object(root["canvas"], "$.canvas", _EVIDENCE_CANVAS_FIELDS)
    try:
        canvas = Canvas(canvas_document["width"], canvas_document["height"])
    except (TypeError, ValueError) as exc:
        _fail("invalid_evidence", "$.canvas", f"invalid evidence canvas: {exc}")
    current_digest = _canvas_sha256(canvas)

    records = _require_exact_array(root["stages"], "$.stages")
    if len(records) != len(STAGE_SEQUENCE_V1):
        _fail("invalid_evidence", "$.stages", "must contain exactly six stage records")

    prior_stage: StageInputIdV1 = "art_intent"
    for index, expected_stage in enumerate(STAGE_SEQUENCE_V1):
        record_path = f"$.stages[{index}]"
        record = _require_exact_object(records[index], record_path, _TRANSITION_FIELDS)
        if record["stage"] != expected_stage:
            _fail(
                "invalid_evidence_order",
                f"{record_path}.stage",
                f"expected {expected_stage!r}",
            )
        if record["input_stage"] != prior_stage:
            _fail(
                "invalid_input_stage",
                f"{record_path}.input_stage",
                f"expected {prior_stage!r}",
            )
        input_digest = _validate_sha256(
            record["input_rgba_sha256"],
            f"{record_path}.input_rgba_sha256",
        )
        if input_digest != current_digest:
            _fail(
                "input_digest_mismatch",
                f"{record_path}.input_rgba_sha256",
                "recorded input digest does not match replay state",
            )

        status = record["status"]
        program = record["program"]
        if status == "applied":
            if record["skip_reason"] is not None:
                _fail(
                    "invalid_applied_record",
                    f"{record_path}.skip_reason",
                    "applied evidence must use null skip_reason",
                )
            if program is None:
                _fail(
                    "missing_program",
                    f"{record_path}.program",
                    "applied evidence requires a PixelProgram",
                )
            try:
                canonical_program = serialize_pixel_program(program)
            except ValueError as exc:
                _fail(
                    "invalid_program",
                    f"{record_path}.program",
                    f"PixelProgram serialization/validation failed: {exc}",
                )
            program_digest = _sha256(canonical_program)
            if _validate_sha256(
                record["program_sha256"],
                f"{record_path}.program_sha256",
            ) != program_digest:
                _fail(
                    "program_digest_mismatch",
                    f"{record_path}.program_sha256",
                    "recorded PixelProgram digest does not match program bytes",
                )

            validated_program = cast(PixelProgramV1, program)
            operation_count, edit_count, touched_bounds = _program_stats(validated_program)
            if record["operation_count"] != operation_count:
                _fail(
                    "operation_count_mismatch",
                    f"{record_path}.operation_count",
                    "recorded operation count does not match PixelProgram",
                )
            if record["edit_count"] != edit_count:
                _fail(
                    "edit_count_mismatch",
                    f"{record_path}.edit_count",
                    "recorded edit count does not match PixelProgram",
                )
            if record["touched_bounds"] != touched_bounds:
                _fail(
                    "touched_bounds_mismatch",
                    f"{record_path}.touched_bounds",
                    "recorded touched bounds do not match serialized edits",
                )
            try:
                apply_pixel_program(canvas, program)
            except PixelProgramCanvasMismatchError as exc:
                _fail("canvas_mismatch", f"{record_path}.program.canvas", str(exc))
        elif status == "skipped":
            _validate_skip_reason(record["skip_reason"], f"{record_path}.skip_reason")
            if program is not None or record["program_sha256"] is not None:
                _fail(
                    "invalid_skip_record",
                    record_path,
                    "skipped evidence must not carry a PixelProgram",
                )
            if (
                record["operation_count"] != 0
                or record["edit_count"] != 0
                or record["touched_bounds"] is not None
            ):
                _fail(
                    "invalid_skip_record",
                    record_path,
                    "skipped evidence must record zero operations/edits and null touched_bounds",
                )
        else:
            _fail(
                "invalid_status",
                f"{record_path}.status",
                "must be 'applied' or 'skipped'",
            )

        current_digest = _canvas_sha256(canvas)
        output_digest = _validate_sha256(
            record["output_rgba_sha256"],
            f"{record_path}.output_rgba_sha256",
        )
        if output_digest != current_digest:
            _fail(
                "output_digest_mismatch",
                f"{record_path}.output_rgba_sha256",
                "recorded output digest does not match replay state",
            )

        preview = record["preview"]
        if preview is not None:
            preview_path = f"{record_path}.preview"
            preview_record = _require_exact_object(preview, preview_path, _PREVIEW_FIELDS)
            if preview_record["kind"] != "nearest-preview":
                _fail(
                    "invalid_preview_evidence",
                    f"{preview_path}.kind",
                    "must be 'nearest-preview'",
                )
            _validate_sha256(preview_record["png_sha256"], f"{preview_path}.png_sha256")
            try:
                exported = export_nearest_preview_png(canvas, scale=preview_record["scale"])
            except (TypeError, ValueError) as exc:
                _fail(
                    "invalid_preview_evidence",
                    f"{preview_path}.scale",
                    f"invalid preview scale: {exc}",
                )
            if (
                preview_record["width"] != exported.metadata.width
                or preview_record["height"] != exported.metadata.height
                or preview_record["png_sha256"] != exported.metadata.png_sha256
            ):
                _fail(
                    "preview_digest_mismatch",
                    preview_path,
                    "preview metadata does not match deterministic replay export",
                )

        prior_stage = cast(StageInputIdV1, expected_stage)

    if final_digest != current_digest:
        _fail(
            "final_digest_mismatch",
            "$.final_rgba_sha256",
            "final digest does not match replay state",
        )
    return canvas
