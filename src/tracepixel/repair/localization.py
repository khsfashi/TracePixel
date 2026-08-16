from __future__ import annotations

from typing import Literal, TypedDict

from tracepixel.model.stage_plan import StageIdV1
from tracepixel.repair.feedback import FeedbackIntakeV1, FeedbackRegionV1

FEEDBACK_LOCALIZATION_SCHEMA_V1 = "tracepixel.feedback-localization.v1"

StageLocalizationBasisV1 = Literal["source_hint", "full_pipeline_fallback"]
RegionLocalizationBasisV1 = Literal["source_hint", "full_canvas_fallback"]


class FeedbackLocalizationItemV1(TypedDict):
    """Explicit bounded stage/region scope for one validated F0 feedback item."""

    feedback_id: str
    affected_stages: list[StageIdV1]
    affected_region: FeedbackRegionV1
    stage_basis: StageLocalizationBasisV1
    region_basis: RegionLocalizationBasisV1


class FeedbackLocalizationV1(TypedDict):
    """Closed P7-F1 envelope retaining the original F0 intake unchanged."""

    schema: Literal["tracepixel.feedback-localization.v1"]
    intake: FeedbackIntakeV1
    localizations: list[FeedbackLocalizationItemV1]
