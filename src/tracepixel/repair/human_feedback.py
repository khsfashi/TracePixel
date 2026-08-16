from __future__ import annotations

from typing import Literal, TypedDict

from .evidence import RepairEvidenceV1
from .feedback import FeedbackIntakeV1

HUMAN_FEEDBACK_SCHEMA_V1 = "tracepixel.human-feedback.v1"
MAX_HUMAN_REVIEW_SOURCE_CHARS_V1 = 512
MAX_HUMAN_REVIEW_SUMMARY_CHARS_V1 = 4096

HumanReviewDecisionV1 = Literal["accept", "request_repair"]
DeterministicQaReviewStatusV1 = Literal["no-findings", "findings-present"]
HumanAuthoringStatusV1 = Literal["accepted", "repair-requested"]


class HumanFeedbackReviewV1(TypedDict):
    """One explicit repository-owner judgment over exact P7-F4 evidence."""

    source_ref: str
    decision: HumanReviewDecisionV1
    summary: str


class HumanFeedbackCompletionV1(TypedDict):
    """Keep deterministic and human completion states separate; define no composite winner."""

    deterministic_qa_status: DeterministicQaReviewStatusV1
    human_authoring_status: HumanAuthoringStatusV1
    composite_completion: Literal["not-defined"]


class HumanFeedbackAuthorityV1(TypedDict):
    human: Literal["repository-owner"]
    deterministic_qa: Literal["retained-not-overridden"]
    perceptual: Literal["owner-human-only"]
    vlm: Literal["not-used"]


class HumanFeedbackV1(TypedDict):
    """P7-F5 review bound to F4 evidence, optionally closing the repair loop into F0."""

    schema: Literal["tracepixel.human-feedback.v1"]
    evidence: RepairEvidenceV1
    evidence_manifest_sha256: str
    review: HumanFeedbackReviewV1
    feedback_intake: FeedbackIntakeV1 | None
    completion: HumanFeedbackCompletionV1
    authority: HumanFeedbackAuthorityV1
