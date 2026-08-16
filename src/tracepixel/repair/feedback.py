from __future__ import annotations

from typing import Literal, TypedDict

from tracepixel.model.stage_plan import StageIdV1
from tracepixel.qa import QaCategoryV1, QaRuleIdV1, QaSeverityV1

FEEDBACK_INTAKE_SCHEMA_V1 = "tracepixel.feedback-intake.v1"
MAX_FEEDBACK_ITEMS_V1 = 32
MAX_FEEDBACK_TEXT_CHARS_V1 = 512

FeedbackAuthorityV1 = Literal["deterministic_qa", "owner_human"]
HumanScoreDimensionV1 = Literal[
    "recognizability",
    "native_1x_readability",
    "style_coherence",
]


class FeedbackCanvasV1(TypedDict):
    width: int
    height: int


class FeedbackTargetV1(TypedDict):
    """Exact logical/artifact target that later repair phases may localize."""

    asset_id: str
    task_id: str
    canvas: FeedbackCanvasV1
    artifact_sha256: str | None


class FeedbackRegionV1(TypedDict):
    """Optional top-left, half-open region hint; not authoritative localization."""

    x: int
    y: int
    width: int
    height: int


class DeterministicQaEvidenceV1(TypedDict):
    """Structured deterministic evidence; summary text never replaces these facts."""

    rule: QaRuleIdV1
    category: QaCategoryV1
    severity: QaSeverityV1


class HumanScoreV1(TypedDict):
    dimension: HumanScoreDimensionV1
    value: int


class HumanFeedbackEvidenceV1(TypedDict):
    """Owner evidence retained as human judgment, never deterministic truth."""

    human_rejection: bool | None
    scores: list[HumanScoreV1]


class FeedbackItemV1(TypedDict):
    """One bounded finding or owner feedback item for P7 repair intake."""

    id: str
    authority: FeedbackAuthorityV1
    source_ref: str
    summary: str
    stage_hint: StageIdV1 | None
    region_hint: FeedbackRegionV1 | None
    deterministic_qa: DeterministicQaEvidenceV1 | None
    human: HumanFeedbackEvidenceV1 | None


class FeedbackIntakeV1(TypedDict):
    """Closed P7-F0 envelope separating machine facts from owner perception."""

    schema: Literal["tracepixel.feedback-intake.v1"]
    target: FeedbackTargetV1
    items: list[FeedbackItemV1]
