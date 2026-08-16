"""Bounded targeted-repair contracts."""

from tracepixel.repair.execution import (
    REPAIR_EXECUTION_SCHEMA_V1,
    RepairExecutionItemV1,
    RepairExecutionStatusV1,
    RepairExecutionV1,
    RepairQaEvaluator,
)
from tracepixel.repair.execution_validation import (
    RepairExecutionValidationError,
    execute_repair_plan,
    validate_repair_execution,
)
from tracepixel.repair.feedback import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    MAX_FEEDBACK_ITEMS_V1,
    MAX_FEEDBACK_TEXT_CHARS_V1,
    DeterministicQaEvidenceV1,
    FeedbackAuthorityV1,
    FeedbackIntakeV1,
    FeedbackItemV1,
    FeedbackRegionV1,
    FeedbackTargetV1,
    HumanFeedbackEvidenceV1,
    HumanScoreDimensionV1,
    HumanScoreV1,
)
from tracepixel.repair.feedback_validation import (
    FeedbackIntakeValidationError,
    validate_feedback_intake,
)
from tracepixel.repair.localization import (
    FEEDBACK_LOCALIZATION_SCHEMA_V1,
    FeedbackLocalizationItemV1,
    FeedbackLocalizationV1,
    RegionLocalizationBasisV1,
    StageLocalizationBasisV1,
)
from tracepixel.repair.localization_validation import (
    FeedbackLocalizationValidationError,
    localize_feedback_intake,
    validate_feedback_localization,
)
from tracepixel.repair.plan import (
    MAX_DEFER_REASON_CHARS_V1,
    REPAIR_PLAN_SCHEMA_V1,
    RepairDispositionV1,
    RepairPlanItemV1,
    RepairPlanV1,
    RepairProposalV1,
)
from tracepixel.repair.plan_validation import (
    RepairPlanValidationError,
    create_repair_plan,
    validate_repair_plan,
)

__all__ = [
    "REPAIR_EXECUTION_SCHEMA_V1",
    "RepairExecutionItemV1",
    "RepairExecutionStatusV1",
    "RepairExecutionV1",
    "RepairQaEvaluator",
    "RepairExecutionValidationError",
    "execute_repair_plan",
    "validate_repair_execution",
    "FEEDBACK_INTAKE_SCHEMA_V1",
    "MAX_FEEDBACK_ITEMS_V1",
    "MAX_FEEDBACK_TEXT_CHARS_V1",
    "DeterministicQaEvidenceV1",
    "FeedbackAuthorityV1",
    "FeedbackIntakeV1",
    "FeedbackItemV1",
    "FeedbackRegionV1",
    "FeedbackTargetV1",
    "HumanFeedbackEvidenceV1",
    "HumanScoreDimensionV1",
    "HumanScoreV1",
    "FeedbackIntakeValidationError",
    "validate_feedback_intake",
    "FEEDBACK_LOCALIZATION_SCHEMA_V1",
    "FeedbackLocalizationItemV1",
    "FeedbackLocalizationV1",
    "RegionLocalizationBasisV1",
    "StageLocalizationBasisV1",
    "FeedbackLocalizationValidationError",
    "localize_feedback_intake",
    "validate_feedback_localization",
    "MAX_DEFER_REASON_CHARS_V1",
    "REPAIR_PLAN_SCHEMA_V1",
    "RepairDispositionV1",
    "RepairPlanItemV1",
    "RepairPlanV1",
    "RepairProposalV1",
    "RepairPlanValidationError",
    "create_repair_plan",
    "validate_repair_plan",
]
