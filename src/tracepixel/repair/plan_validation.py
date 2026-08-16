from __future__ import annotations

from typing import cast

from tracepixel.model.pixel_ir import PIXEL_PROGRAM_SCHEMA_V1, PixelProgramV1
from tracepixel.model.stage_plan import StageIdV1
from tracepixel.model.validation import PixelProgramValidationError, validate_pixel_program
from tracepixel.repair.feedback import FeedbackRegionV1
from tracepixel.repair.localization import FeedbackLocalizationItemV1, FeedbackLocalizationV1
from tracepixel.repair.localization_validation import (
    FeedbackLocalizationValidationError,
    validate_feedback_localization,
)

from .plan import (
    MAX_DEFER_REASON_CHARS_V1,
    REPAIR_PLAN_SCHEMA_V1,
    RepairPlanItemV1,
    RepairPlanV1,
)

_ROOT_FIELDS = frozenset(("schema", "localization", "repairs"))
_PROPOSAL_FIELDS = frozenset(("feedback_id", "target_stage", "program", "defer_reason"))
_REPAIR_FIELDS = frozenset(
    (
        "feedback_id",
        "disposition",
        "target_stage",
        "planned_region",
        "repair_program",
        "planned_operation_count",
        "planned_pixel_edit_count",
        "defer_reason",
    )
)
_REGION_FIELDS = frozenset(("x", "y", "width", "height"))


class RepairPlanValidationError(ValueError):
    """Deterministic P7-F2 rejection with stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise RepairPlanValidationError(code, path, message)


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


def _validated_localization(value: object) -> FeedbackLocalizationV1:
    try:
        return validate_feedback_localization(value)
    except FeedbackLocalizationValidationError as exc:
        path = "$.localization" if exc.path == "$" else f"$.localization{exc.path[1:]}"
        _fail(
            "invalid_localization",
            path,
            f"feedback localization validation failed with {exc.code}: {exc.message}",
        )


def _validate_defer_reason(value: object, path: str) -> str:
    if type(value) is not str:
        _fail("invalid_defer_reason", path, "must be a string for a deferred repair")
    reason = cast(str, value)
    if not 1 <= len(reason) <= MAX_DEFER_REASON_CHARS_V1 or not reason.strip():
        _fail(
            "invalid_defer_reason",
            path,
            f"must contain 1..{MAX_DEFER_REASON_CHARS_V1} non-blank characters",
        )
    return reason


def _validate_target_stage(
    value: object,
    localization: FeedbackLocalizationItemV1,
    path: str,
) -> StageIdV1:
    if type(value) is not str or value not in localization["affected_stages"]:
        _fail(
            "stage_outside_localization",
            path,
            "repair target stage must be one of the F1 affected stages",
        )
    return cast(StageIdV1, value)


def _inside_region(x: int, y: int, region: FeedbackRegionV1) -> bool:
    return (
        region["x"] <= x < region["x"] + region["width"]
        and region["y"] <= y < region["y"] + region["height"]
    )


def _planned_region(pixels: list[list[int]]) -> FeedbackRegionV1:
    xs = [pixel[0] for pixel in pixels]
    ys = [pixel[1] for pixel in pixels]
    min_x = min(xs)
    min_y = min(ys)
    return {
        "x": min_x,
        "y": min_y,
        "width": max(xs) - min_x + 1,
        "height": max(ys) - min_y + 1,
    }


def _canonicalize_program(
    value: object,
    *,
    canvas: dict[str, int],
    affected_region: FeedbackRegionV1,
    path: str,
) -> tuple[PixelProgramV1, FeedbackRegionV1, int]:
    try:
        program = validate_pixel_program(value)
    except PixelProgramValidationError as exc:
        rebased = path if exc.path == "$" else f"{path}{exc.path[1:]}"
        _fail(
            "invalid_repair_program",
            rebased,
            f"PixelProgram validation failed with {exc.code}: {exc.message}",
        )

    if program["canvas"] != canvas:
        _fail(
            "canvas_mismatch",
            f"{path}.canvas",
            "repair PixelProgram canvas must equal the F0 target canvas",
        )

    last_write: dict[tuple[int, int], list[int]] = {}
    for operation in program["operations"]:
        for raw_pixel in operation["pixels"]:
            pixel = list(raw_pixel)
            x, y = pixel[0], pixel[1]
            if not _inside_region(x, y, affected_region):
                _fail(
                    "pixel_outside_localization",
                    path,
                    f"repair pixel ({x}, {y}) lies outside the F1 affected region",
                )
            last_write[(x, y)] = pixel

    if not last_write:
        _fail("empty_repair", path, "repair proposal must target at least one pixel")

    canonical_pixels = [
        last_write[coordinate]
        for coordinate in sorted(last_write, key=lambda coordinate: (coordinate[1], coordinate[0]))
    ]
    canonical: PixelProgramV1 = {
        "schema": PIXEL_PROGRAM_SCHEMA_V1,
        "canvas": {"width": canvas["width"], "height": canvas["height"]},
        "operations": [{"op": "set_pixels", "pixels": canonical_pixels}],
    }
    return canonical, _planned_region(canonical_pixels), len(canonical_pixels)


def _validate_region(value: object, path: str) -> FeedbackRegionV1:
    region = _require_exact_object(value, path, _REGION_FIELDS)
    parts = (region["x"], region["y"], region["width"], region["height"])
    if not all(type(part) is int for part in parts):
        _fail("invalid_planned_region", path, "x, y, width and height must be exact integers")
    x, y, width, height = cast(tuple[int, int, int, int], parts)
    if x < 0 or y < 0 or width < 1 or height < 1:
        _fail(
            "invalid_planned_region",
            path,
            "x/y must be non-negative and width/height positive",
        )
    return cast(FeedbackRegionV1, {"x": x, "y": y, "width": width, "height": height})


def create_repair_plan(localization: object, proposals: object) -> RepairPlanV1:
    """Build a canonical minimal F2 plan without executing it.

    Repair proposals may contain multiple set-pixel operations or repeated writes.
    Because PixelProgram v1 has only exact set-pixel writes, F2 deterministically
    collapses each proposal to one operation, keeps the last write per coordinate,
    and sorts the unique coordinates. It never invents edits from feedback prose.
    """

    localized = _validated_localization(localization)
    raw_proposals = _require_array(proposals, "$.proposals")
    if len(raw_proposals) != len(localized["localizations"]):
        _fail(
            "proposal_count_mismatch",
            "$.proposals",
            "must contain exactly one proposal per F1 localization item",
        )

    canvas = localized["intake"]["target"]["canvas"]
    repairs: list[RepairPlanItemV1] = []

    for index, raw_proposal in enumerate(raw_proposals):
        proposal_path = f"$.proposals[{index}]"
        proposal = _require_exact_object(raw_proposal, proposal_path, _PROPOSAL_FIELDS)
        source = localized["localizations"][index]

        feedback_id = proposal["feedback_id"]
        if type(feedback_id) is not str or feedback_id != source["feedback_id"]:
            _fail(
                "feedback_order_mismatch",
                f"{proposal_path}.feedback_id",
                f"must match localization item {source['feedback_id']!r} at the same index",
            )

        program = proposal["program"]
        target_stage = proposal["target_stage"]
        defer_reason = proposal["defer_reason"]

        if program is None:
            if target_stage is not None:
                _fail(
                    "invalid_defer",
                    f"{proposal_path}.target_stage",
                    "deferred repair must not select a target stage",
                )
            reason = _validate_defer_reason(defer_reason, f"{proposal_path}.defer_reason")
            repairs.append(
                {
                    "feedback_id": source["feedback_id"],
                    "disposition": "defer",
                    "target_stage": None,
                    "planned_region": None,
                    "repair_program": None,
                    "planned_operation_count": 0,
                    "planned_pixel_edit_count": 0,
                    "defer_reason": reason,
                }
            )
            continue

        stage = _validate_target_stage(target_stage, source, f"{proposal_path}.target_stage")
        if defer_reason is not None:
            _fail(
                "invalid_repair",
                f"{proposal_path}.defer_reason",
                "active repair must use null defer_reason",
            )
        canonical, planned_region, pixel_count = _canonicalize_program(
            program,
            canvas=canvas,
            affected_region=source["affected_region"],
            path=f"{proposal_path}.program",
        )
        repairs.append(
            {
                "feedback_id": source["feedback_id"],
                "disposition": "repair",
                "target_stage": stage,
                "planned_region": planned_region,
                "repair_program": canonical,
                "planned_operation_count": 1,
                "planned_pixel_edit_count": pixel_count,
                "defer_reason": None,
            }
        )

    return {
        "schema": REPAIR_PLAN_SCHEMA_V1,
        "localization": localized,
        "repairs": repairs,
    }


def validate_repair_plan(value: object) -> RepairPlanV1:
    """Validate closed F2 provenance, bounds, canonical minimal form, and planned cost."""

    root = _require_exact_object(value, "$", _ROOT_FIELDS)
    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != REPAIR_PLAN_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {REPAIR_PLAN_SCHEMA_V1!r}",
        )

    localized = _validated_localization(root["localization"])
    raw_repairs = _require_array(root["repairs"], "$.repairs")
    if len(raw_repairs) != len(localized["localizations"]):
        _fail(
            "repair_count_mismatch",
            "$.repairs",
            "must contain exactly one repair/defer decision per F1 localization item",
        )

    canvas = localized["intake"]["target"]["canvas"]

    for index, raw_repair in enumerate(raw_repairs):
        path = f"$.repairs[{index}]"
        repair = _require_exact_object(raw_repair, path, _REPAIR_FIELDS)
        source = localized["localizations"][index]

        feedback_id = repair["feedback_id"]
        if type(feedback_id) is not str or feedback_id != source["feedback_id"]:
            _fail(
                "feedback_order_mismatch",
                f"{path}.feedback_id",
                f"must match localization item {source['feedback_id']!r} at the same index",
            )

        disposition = repair["disposition"]
        if disposition == "defer":
            if (
                repair["target_stage"] is not None
                or repair["planned_region"] is not None
                or repair["repair_program"] is not None
                or type(repair["planned_operation_count"]) is not int
                or repair["planned_operation_count"] != 0
                or type(repair["planned_pixel_edit_count"]) is not int
                or repair["planned_pixel_edit_count"] != 0
            ):
                _fail(
                    "invalid_defer",
                    path,
                    "deferred item must have null repair fields and zero planned cost",
                )
            _validate_defer_reason(repair["defer_reason"], f"{path}.defer_reason")
            continue

        if disposition != "repair":
            _fail(
                "invalid_disposition",
                f"{path}.disposition",
                "must be either 'repair' or 'defer'",
            )

        _validate_target_stage(repair["target_stage"], source, f"{path}.target_stage")
        if repair["defer_reason"] is not None:
            _fail(
                "invalid_repair",
                f"{path}.defer_reason",
                "active repair must use null defer_reason",
            )
        if repair["repair_program"] is None:
            _fail("invalid_repair", f"{path}.repair_program", "active repair requires a PixelProgram")

        canonical, expected_region, expected_pixel_count = _canonicalize_program(
            repair["repair_program"],
            canvas=canvas,
            affected_region=source["affected_region"],
            path=f"{path}.repair_program",
        )
        if repair["repair_program"] != canonical:
            _fail(
                "nonminimal_program",
                f"{path}.repair_program",
                "repair program must be canonical: one set_pixels operation, unique coordinates, stable y/x order",
            )

        if type(repair["planned_operation_count"]) is not int or repair["planned_operation_count"] != 1:
            _fail(
                "planned_cost_mismatch",
                f"{path}.planned_operation_count",
                "canonical active repair must report exactly one planned operation",
            )
        if (
            type(repair["planned_pixel_edit_count"]) is not int
            or repair["planned_pixel_edit_count"] != expected_pixel_count
        ):
            _fail(
                "planned_cost_mismatch",
                f"{path}.planned_pixel_edit_count",
                f"must equal canonical unique pixel edit count {expected_pixel_count}",
            )

        if repair["planned_region"] is None:
            _fail("planned_region_mismatch", f"{path}.planned_region", "active repair requires a region")
        planned_region = _validate_region(repair["planned_region"], f"{path}.planned_region")
        if planned_region != expected_region:
            _fail(
                "planned_region_mismatch",
                f"{path}.planned_region",
                "must equal the exact bounding box of canonical planned pixel edits",
            )

    return cast(RepairPlanV1, value)
