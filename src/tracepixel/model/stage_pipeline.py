from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from tracepixel.raster import Canvas, PngExportMetadata, export_nearest_preview_png

from .art_intent import ArtIntentV1
from .execution import PixelProgramCanvasMismatchError, _apply_validated_pixel_program
from .stage_evidence import (
    STAGE_PIPELINE_EVIDENCE_SCHEMA_V1,
    StagePipelineEvidenceV1,
    StagePreviewEvidenceV1,
    StageTransitionEvidenceV1,
    _canonical_json_bytes,
    _canvas_sha256,
    _preview_evidence,
    _program_stats,
    _sha256,
)
from .stage_plan import (
    StageIdV1,
    StageInputIdV1,
    StageStatusV1,
    _fail,
    _program_for_document,
    validate_stage_plan,
)
from .serialization import serialize_pixel_program


@dataclass(frozen=True, slots=True)
class StagePreviewSnapshot:
    stage: StageIdV1
    png: bytes
    metadata: PngExportMetadata


@dataclass(frozen=True, slots=True)
class StagePipelineResult:
    canvas: Canvas
    evidence: StagePipelineEvidenceV1
    previews: tuple[StagePreviewSnapshot, ...]


def execute_stage_pipeline(
    art_intent: object,
    stage_plan: object,
    *,
    preview_scale: int | None = None,
) -> StagePipelineResult:
    """Validate and apply S1-S6 in order to one authoritative Canvas with evidence."""

    plan = validate_stage_plan(stage_plan, art_intent=art_intent)
    intent = cast(ArtIntentV1, art_intent)
    canvas = Canvas(intent["canvas"]["width"], intent["canvas"]["height"])
    current_digest = _canvas_sha256(canvas)
    prior_stage: StageInputIdV1 = "art_intent"
    records: list[StageTransitionEvidenceV1] = []
    previews: list[StagePreviewSnapshot] = []

    for entry in plan["stages"]:
        stage_id = entry["stage"]
        input_digest = current_digest
        document = entry["document"]

        if document is None:
            status: StageStatusV1 = "skipped"
            skip_reason = cast(str, entry["skip_reason"])
            program = None
            program_sha256 = None
            operation_count = 0
            edit_count = 0
            touched_bounds = None
        else:
            status = "applied"
            skip_reason = None
            program = _program_for_document(document)
            program_sha256 = _sha256(serialize_pixel_program(program))
            operation_count, edit_count, touched_bounds = _program_stats(program)
            try:
                _apply_validated_pixel_program(canvas, program)
            except PixelProgramCanvasMismatchError as exc:
                _fail(
                    "canvas_mismatch",
                    f"$.stages[{len(records)}].document.program.canvas",
                    str(exc),
                )

        preview: StagePreviewEvidenceV1 | None = None
        if preview_scale is None:
            current_digest = _canvas_sha256(canvas)
        else:
            exported = export_nearest_preview_png(canvas, scale=preview_scale)
            current_digest = exported.metadata.authoritative_rgba_sha256
            preview = _preview_evidence(exported.metadata)
            previews.append(
                StagePreviewSnapshot(
                    stage=stage_id,
                    png=exported.png,
                    metadata=exported.metadata,
                )
            )

        records.append(
            {
                "stage": stage_id,
                "input_stage": prior_stage,
                "status": status,
                "skip_reason": skip_reason,
                "input_rgba_sha256": input_digest,
                "output_rgba_sha256": current_digest,
                "program": program,
                "program_sha256": program_sha256,
                "operation_count": operation_count,
                "edit_count": edit_count,
                "touched_bounds": touched_bounds,
                "preview": preview,
            }
        )
        prior_stage = cast(StageInputIdV1, stage_id)

    evidence: StagePipelineEvidenceV1 = {
        "schema": STAGE_PIPELINE_EVIDENCE_SCHEMA_V1,
        "art_intent_sha256": _sha256(_canonical_json_bytes(intent)),
        "stage_plan_sha256": _sha256(_canonical_json_bytes(plan)),
        "canvas": {"width": canvas.width, "height": canvas.height},
        "stages": records,
        "final_rgba_sha256": current_digest,
    }
    return StagePipelineResult(canvas=canvas, evidence=evidence, previews=tuple(previews))
