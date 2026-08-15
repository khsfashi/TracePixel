from __future__ import annotations

from typing import Literal, TypedDict, cast

from .art_intent import ArtIntentV1
from .art_intent_validation import ArtIntentValidationError, validate_art_intent
from .major_forms_stage import MajorFormsStageV1
from .major_forms_stage_validation import (
    MajorFormsStageValidationError,
    validate_major_forms_stage,
)
from .outline_cleanup_stage import OutlineCleanupStageV1
from .outline_cleanup_stage_validation import (
    OutlineCleanupStageValidationError,
    validate_outline_cleanup_stage,
)
from .palette_light_stage import PaletteLightStageV1
from .palette_light_stage_validation import (
    PaletteLightStageValidationError,
    validate_palette_light_stage,
)
from .pixel_ir import PixelProgramV1
from .semantic_details_stage import SemanticDetailsStageV1
from .semantic_details_stage_validation import (
    SemanticDetailsStageValidationError,
    validate_semantic_details_stage,
)
from .shading_stage import ShadingStageV1
from .shading_stage_validation import ShadingStageValidationError, validate_shading_stage
from .silhouette_stage import SilhouetteStageV1
from .silhouette_stage_validation import (
    SilhouetteStageValidationError,
    validate_silhouette_stage,
)

STAGE_PLAN_SCHEMA_V1 = "tracepixel.stage-plan.v1"

StageIdV1 = Literal[
    "silhouette",
    "major_forms",
    "palette_light_ramp",
    "shading",
    "semantic_details",
    "outline_cleanup",
]
StageInputIdV1 = Literal[
    "art_intent",
    "silhouette",
    "major_forms",
    "palette_light_ramp",
    "shading",
    "semantic_details",
]
StageStatusV1 = Literal["applied", "skipped"]

STAGE_SEQUENCE_V1: tuple[StageIdV1, ...] = (
    "silhouette",
    "major_forms",
    "palette_light_ramp",
    "shading",
    "semantic_details",
    "outline_cleanup",
)

StageDocumentV1 = (
    SilhouetteStageV1
    | MajorFormsStageV1
    | PaletteLightStageV1
    | ShadingStageV1
    | SemanticDetailsStageV1
    | OutlineCleanupStageV1
)


class StagePlanEntryV1(TypedDict):
    """One fixed-order S1-S6 choice: execute a stage document or skip it explicitly."""

    stage: StageIdV1
    document: StageDocumentV1 | None
    skip_reason: str | None


class StagePlanV1(TypedDict):
    """Closed, provider-neutral P3-S7 execution plan."""

    schema: Literal["tracepixel.stage-plan.v1"]
    stages: list[StagePlanEntryV1]


class StagePipelineValidationError(ValueError):
    """Deterministic P3-S7 rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise StagePipelineValidationError(code, path, message)


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
    actual = frozenset(cast(dict[str, object], obj))
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail("invalid_fields", path, "; ".join(parts))
    return cast(dict[str, object], obj)


def _require_exact_array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def _rebase_document_path(index: int, path: str) -> str:
    prefix = f"$.stages[{index}].document"
    if path == "$":
        return prefix
    if path.startswith("$"):
        return f"{prefix}{path[1:]}"
    return prefix


def _validate_skip_reason(value: object, path: str) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string when a stage is skipped")
    reason = cast(str, value)
    if not 1 <= len(reason) <= 128 or not reason.strip():
        _fail(
            "invalid_skip_reason",
            path,
            "skip reason must contain 1..128 characters and must not be blank",
        )
    return reason


def _program_for_document(document: StageDocumentV1) -> PixelProgramV1:
    return document["program"]


def _validate_stage_document(
    expected_stage: StageIdV1,
    document: object,
    *,
    index: int,
    art_intent: ArtIntentV1,
    palette_light_stage: PaletteLightStageV1 | None,
) -> StageDocumentV1:
    try:
        if expected_stage == "silhouette":
            validated = validate_silhouette_stage(document)
        elif expected_stage == "major_forms":
            validated = validate_major_forms_stage(document)
        elif expected_stage == "palette_light_ramp":
            validated = validate_palette_light_stage(document)
        elif expected_stage == "shading":
            if palette_light_stage is None:
                _fail(
                    "missing_stage_context",
                    f"$.stages[{index}].document",
                    "applied shading requires an applied palette/light stage",
                )
            validated = validate_shading_stage(
                document,
                art_intent=art_intent,
                palette_light_stage=palette_light_stage,
            )
        elif expected_stage == "semantic_details":
            if palette_light_stage is None:
                _fail(
                    "missing_stage_context",
                    f"$.stages[{index}].document",
                    "applied semantic details require an applied palette/light stage",
                )
            validated = validate_semantic_details_stage(
                document,
                palette_light_stage=palette_light_stage,
            )
        else:
            if palette_light_stage is None:
                _fail(
                    "missing_stage_context",
                    f"$.stages[{index}].document",
                    "applied outline/cleanup requires an applied palette/light stage",
                )
            validated = validate_outline_cleanup_stage(
                document,
                palette_light_stage=palette_light_stage,
            )
    except StagePipelineValidationError:
        raise
    except (
        SilhouetteStageValidationError,
        MajorFormsStageValidationError,
        PaletteLightStageValidationError,
        ShadingStageValidationError,
        SemanticDetailsStageValidationError,
        OutlineCleanupStageValidationError,
    ) as exc:
        _fail(
            "invalid_stage_document",
            _rebase_document_path(index, exc.path),
            f"stage validator rejected with {exc.code}: {exc.message}",
        )

    validated_document = cast(StageDocumentV1, validated)
    if validated_document["stage"] != expected_stage:
        _fail(
            "stage_document_mismatch",
            f"$.stages[{index}].document.stage",
            f"document stage must be exactly {expected_stage!r}",
        )
    if validated_document["program"]["canvas"] != art_intent["canvas"]:
        _fail(
            "canvas_mismatch",
            f"$.stages[{index}].document.program.canvas",
            "every applied stage PixelProgram canvas must equal ArtIntent canvas",
        )
    return validated_document


def validate_stage_plan(stage_plan: object, *, art_intent: object) -> StagePlanV1:
    """Validate fixed order, explicit skip semantics, palette budget and stage context."""

    try:
        intent = validate_art_intent(art_intent)
    except ArtIntentValidationError as exc:
        path = "$context.art_intent" if exc.path == "$" else f"$context.art_intent{exc.path[1:]}"
        _fail(
            "invalid_art_intent",
            path,
            f"ArtIntent validation failed with {exc.code}: {exc.message}",
        )

    root = _require_exact_object(stage_plan, "$", frozenset(("schema", "stages")))
    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != STAGE_PLAN_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {STAGE_PLAN_SCHEMA_V1!r}",
        )

    entries = _require_exact_array(root["stages"], "$.stages")
    if len(entries) != len(STAGE_SEQUENCE_V1):
        _fail(
            "invalid_stage_count",
            "$.stages",
            f"stage plan must contain exactly {len(STAGE_SEQUENCE_V1)} fixed S1-S6 entries",
        )

    validated_intent = cast(ArtIntentV1, intent)
    palette_context: PaletteLightStageV1 | None = None

    for index, expected_stage in enumerate(STAGE_SEQUENCE_V1):
        entry_path = f"$.stages[{index}]"
        entry = _require_exact_object(
            entries[index],
            entry_path,
            frozenset(("stage", "document", "skip_reason")),
        )

        stage_id = entry["stage"]
        if type(stage_id) is not str:
            _fail("invalid_type", f"{entry_path}.stage", "must be a string")
        if stage_id != expected_stage:
            _fail(
                "invalid_stage_order",
                f"{entry_path}.stage",
                f"expected fixed stage {expected_stage!r}, got {stage_id!r}",
            )

        document = entry["document"]
        skip_reason = entry["skip_reason"]
        if document is None:
            _validate_skip_reason(skip_reason, f"{entry_path}.skip_reason")
            continue
        if skip_reason is not None:
            _fail(
                "ambiguous_stage_action",
                f"{entry_path}.skip_reason",
                "applied stage must use null skip_reason",
            )

        validated_document = _validate_stage_document(
            expected_stage,
            document,
            index=index,
            art_intent=validated_intent,
            palette_light_stage=palette_context,
        )
        if expected_stage == "palette_light_ramp":
            palette_context = cast(PaletteLightStageV1, validated_document)
            palette_budget = validated_intent["composition"]["palette_budget"]
            if palette_budget is not None and len(palette_context["palette"]) > palette_budget:
                _fail(
                    "palette_budget_exceeded",
                    f"{entry_path}.document.palette",
                    f"declared palette has {len(palette_context['palette'])} colors but ArtIntent budget is {palette_budget}",
                )

    return cast(StagePlanV1, stage_plan)
