from __future__ import annotations

from typing import Literal, TypedDict

from tracepixel.model.pixel_ir import PixelProgramV1
from tracepixel.model.stage_plan import StageIdV1
from tracepixel.repair.feedback import FeedbackRegionV1
from tracepixel.repair.localization import FeedbackLocalizationV1

REPAIR_PLAN_SCHEMA_V1 = "tracepixel.repair-plan.v1"
MAX_DEFER_REASON_CHARS_V1 = 256

RepairDispositionV1 = Literal["repair", "defer"]


class RepairProposalV1(TypedDict):
    """Explicit F2 proposal. The planner normalizes repair programs deterministically."""

    feedback_id: str
    target_stage: StageIdV1 | None
    program: PixelProgramV1 | None
    defer_reason: str | None


class RepairPlanItemV1(TypedDict):
    """One bounded repair/defer decision tied to one F1 localization item."""

    feedback_id: str
    disposition: RepairDispositionV1
    target_stage: StageIdV1 | None
    planned_region: FeedbackRegionV1 | None
    repair_program: PixelProgramV1 | None
    planned_operation_count: int
    planned_pixel_edit_count: int
    defer_reason: str | None


class RepairPlanV1(TypedDict):
    """Closed P7-F2 plan retaining the exact F1 localization provenance."""

    schema: Literal["tracepixel.repair-plan.v1"]
    localization: FeedbackLocalizationV1
    repairs: list[RepairPlanItemV1]
