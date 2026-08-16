from __future__ import annotations

from typing import cast

from tracepixel.model.stage_plan import STAGE_SEQUENCE_V1, StageIdV1
from tracepixel.raster.contract import CanvasSizeError, CanvasSpec
from tracepixel.repair.feedback import FeedbackIntakeV1, FeedbackItemV1
from tracepixel.repair.feedback_validation import (
    FeedbackIntakeValidationError,
    validate_feedback_intake,
)

from .localization import (
    FEEDBACK_LOCALIZATION_SCHEMA_V1,
    FeedbackLocalizationItemV1,
    FeedbackLocalizationV1,
)

_ROOT_FIELDS = frozenset(("schema", "intake", "localizations"))
_LOCALIZATION_FIELDS = frozenset(
    ("feedback_id", "affected_stages", "affected_region", "stage_basis", "region_basis")
)
_REGION_FIELDS = frozenset(("x", "y", "width", "height"))
_STAGE_BASIS = frozenset(("source_hint", "full_pipeline_fallback"))
_REGION_BASIS = frozenset(("source_hint", "full_canvas_fallback"))
_STAGE_INDEX = {stage: index for index, stage in enumerate(STAGE_SEQUENCE_V1)}


class FeedbackLocalizationValidationError(ValueError):
    """Deterministic P7-F1 rejection with stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise FeedbackLocalizationValidationError(code, path, message)


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


def _require_array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def _rebase_intake_path(path: str) -> str:
    if path == "$":
        return "$.intake"
    if path.startswith("$"):
        return f"$.intake{path[1:]}"
    return "$.intake"


def _validated_intake(value: object) -> FeedbackIntakeV1:
    try:
        return validate_feedback_intake(value)
    except FeedbackIntakeValidationError as exc:
        _fail(
            "invalid_intake",
            _rebase_intake_path(exc.path),
            f"feedback intake validation failed with {exc.code}: {exc.message}",
        )


def _canvas_spec(intake: FeedbackIntakeV1) -> CanvasSpec:
    canvas = intake["target"]["canvas"]
    try:
        return CanvasSpec(canvas["width"], canvas["height"])
    except CanvasSizeError as exc:
        _fail("invalid_intake", "$.intake.target.canvas", str(exc))


def _expected_stage_scope(item: FeedbackItemV1) -> tuple[list[StageIdV1], str]:
    stage_hint = item["stage_hint"]
    if stage_hint is not None:
        return [stage_hint], "source_hint"
    return list(STAGE_SEQUENCE_V1), "full_pipeline_fallback"


def _expected_region(
    item: FeedbackItemV1,
    spec: CanvasSpec,
) -> tuple[dict[str, int], str]:
    region_hint = item["region_hint"]
    if region_hint is not None:
        return dict(region_hint), "source_hint"
    return {
        "x": 0,
        "y": 0,
        "width": spec.width,
        "height": spec.height,
    }, "full_canvas_fallback"


def _validate_stage_scope(value: object, path: str) -> list[StageIdV1]:
    raw_stages = _require_array(value, path)
    if not 1 <= len(raw_stages) <= len(STAGE_SEQUENCE_V1):
        _fail(
            "invalid_stage_count",
            path,
            f"must contain 1..{len(STAGE_SEQUENCE_V1)} affected stages",
        )

    stages: list[StageIdV1] = []
    seen: set[str] = set()
    for index, raw_stage in enumerate(raw_stages):
        stage_path = f"{path}[{index}]"
        if type(raw_stage) is not str or raw_stage not in _STAGE_INDEX:
            _fail("invalid_stage", stage_path, f"unsupported stage {raw_stage!r}")
        stage = cast(StageIdV1, raw_stage)
        if stage in seen:
            _fail("duplicate_stage", stage_path, "affected stages must be unique")
        seen.add(stage)
        stages.append(stage)

    if stages != sorted(stages, key=lambda stage: _STAGE_INDEX[stage]):
        _fail("invalid_stage_order", path, "affected stages must use canonical P3 stage order")
    return stages


def _validate_region(value: object, path: str, spec: CanvasSpec) -> dict[str, int]:
    region = _require_exact_object(value, path, _REGION_FIELDS)
    parts = (region["x"], region["y"], region["width"], region["height"])
    if not all(type(part) is int for part in parts):
        _fail("invalid_region", path, "x, y, width and height must be exact integers")
    x, y, width, height = cast(tuple[int, int, int, int], parts)
    if x < 0 or y < 0 or width < 1 or height < 1:
        _fail("invalid_region", path, "x/y must be non-negative and width/height positive")
    if x + width > spec.width or y + height > spec.height:
        _fail("invalid_region", path, "affected region must fit inside target canvas")
    return {"x": x, "y": y, "width": width, "height": height}


def localize_feedback_intake(value: object) -> FeedbackLocalizationV1:
    """Promote explicit F0 hints into mandatory scopes; otherwise widen conservatively.

    P7-F1 never parses human prose, owner scores, rejection state, or QA rule ids to
    manufacture localization precision. Missing stage evidence becomes the full P3
    pipeline; missing region evidence becomes the full target canvas.
    """

    intake = _validated_intake(value)
    spec = _canvas_spec(intake)
    localizations: list[FeedbackLocalizationItemV1] = []

    for item in intake["items"]:
        affected_stages, stage_basis = _expected_stage_scope(item)
        affected_region, region_basis = _expected_region(item, spec)
        localizations.append(
            {
                "feedback_id": item["id"],
                "affected_stages": affected_stages,
                "affected_region": cast(dict[str, int], affected_region),
                "stage_basis": cast(str, stage_basis),
                "region_basis": cast(str, region_basis),
            }
        )

    return {
        "schema": FEEDBACK_LOCALIZATION_SCHEMA_V1,
        "intake": intake,
        "localizations": localizations,
    }


def validate_feedback_localization(value: object) -> FeedbackLocalizationV1:
    """Validate a closed P7-F1 result and its exact deterministic F0-derived scopes."""

    root = _require_exact_object(value, "$", _ROOT_FIELDS)
    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != FEEDBACK_LOCALIZATION_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {FEEDBACK_LOCALIZATION_SCHEMA_V1!r}",
        )

    intake = _validated_intake(root["intake"])
    spec = _canvas_spec(intake)
    localizations = _require_array(root["localizations"], "$.localizations")
    if len(localizations) != len(intake["items"]):
        _fail(
            "localization_count_mismatch",
            "$.localizations",
            "must contain exactly one localization per feedback item",
        )

    for index, raw_localization in enumerate(localizations):
        path = f"$.localizations[{index}]"
        localization = _require_exact_object(raw_localization, path, _LOCALIZATION_FIELDS)
        source_item = intake["items"][index]

        feedback_id = localization["feedback_id"]
        if type(feedback_id) is not str or feedback_id != source_item["id"]:
            _fail(
                "feedback_order_mismatch",
                f"{path}.feedback_id",
                f"must match intake item {source_item['id']!r} at the same index",
            )

        stages = _validate_stage_scope(localization["affected_stages"], f"{path}.affected_stages")
        expected_stages, expected_stage_basis = _expected_stage_scope(source_item)

        stage_basis = localization["stage_basis"]
        if type(stage_basis) is not str or stage_basis not in _STAGE_BASIS:
            _fail("invalid_stage_basis", f"{path}.stage_basis", f"unsupported basis {stage_basis!r}")
        if stages != expected_stages or stage_basis != expected_stage_basis:
            _fail(
                "stage_scope_mismatch",
                path,
                "stage scope/basis must be exactly derived from the source hint or conservative fallback",
            )

        region = _validate_region(localization["affected_region"], f"{path}.affected_region", spec)
        expected_region, expected_region_basis = _expected_region(source_item, spec)

        region_basis = localization["region_basis"]
        if type(region_basis) is not str or region_basis not in _REGION_BASIS:
            _fail(
                "invalid_region_basis",
                f"{path}.region_basis",
                f"unsupported basis {region_basis!r}",
            )
        if region != expected_region or region_basis != expected_region_basis:
            _fail(
                "region_scope_mismatch",
                path,
                "region scope/basis must be exactly derived from the source hint or conservative fallback",
            )

    return cast(FeedbackLocalizationV1, value)
