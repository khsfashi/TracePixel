from __future__ import annotations

from typing import Literal, Protocol, TypedDict, runtime_checkable

from tracepixel.model.stage_plan import StageIdV1
from tracepixel.qa import QaFindingsV1
from tracepixel.raster import Canvas

from .plan import RepairPlanV1

REPAIR_EXECUTION_SCHEMA_V1 = "tracepixel.repair-execution.v1"

RepairExecutionStatusV1 = Literal["applied", "deferred"]


class RepairExecutionItemV1(TypedDict):
    """Observed execution cost for one ordered F2 repair/defer item."""

    feedback_id: str
    status: RepairExecutionStatusV1
    target_stage: StageIdV1 | None
    applied_operation_count: int
    applied_pixel_edit_count: int
    observed_changed_pixel_count: int


class RepairExecutionV1(TypedDict):
    """P7-F3 execution/QA evidence retaining the exact F2 plan provenance."""

    schema: Literal["tracepixel.repair-execution.v1"]
    plan: RepairPlanV1
    source_rgba_sha256: str
    result_rgba_sha256: str
    executions: list[RepairExecutionItemV1]
    applied_operation_count: int
    applied_pixel_edit_count: int
    observed_changed_pixel_count: int
    unaffected_region_stable: bool
    qa: QaFindingsV1


@runtime_checkable
class RepairQaEvaluator(Protocol):
    """Provider-free deterministic QA boundary used after bounded repair execution."""

    def evaluate(self, canvas: Canvas, /) -> QaFindingsV1:
        ...
