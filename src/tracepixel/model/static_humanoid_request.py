from __future__ import annotations

from typing import Literal, TypedDict

from .humanoid_pose import HumanoidPoseRefV1
from .humanoid_profile import HumanoidProfileRefV1

STATIC_HUMANOID_REQUEST_SCHEMA_V1 = "tracepixel.static-humanoid-request.v1"
STATIC_HUMANOID_EVIDENCE_POLICY_SCHEMA_V1 = "tracepixel.static-humanoid-evidence-policy.v1"

DETERMINISTIC_EVIDENCE_FACTS_V1 = (
    "schema-and-version-identity",
    "digest-binding",
    "finite-range-validity",
    "body-landmark-reference-integrity",
    "equipment-anchor-reference-integrity",
    "declared-required-relation-satisfaction-when-structured",
    "support-contact-declarations",
    "declared-orientation-and-attachment-side-intent",
    "existing-raster-and-qa-facts",
    "provider-cost-and-provenance-accounting",
)

PERCEPTUAL_EVIDENCE_FACTS_V1 = (
    "humanoid-recognizability",
    "anatomy-believability-for-stylization",
    "pose-intent-readability",
    "identity-coherence",
    "silhouette-readability",
    "equipment-readability",
    "visual-style-coherence",
)


class StaticHumanoidEvidencePolicyV1(TypedDict):
    """Frozen H3 authority split. Perceptual facts never become deterministic correctness."""

    schema: Literal["tracepixel.static-humanoid-evidence-policy.v1"]
    deterministic_facts: list[str]
    perceptual_facts: list[str]
    vlm_is_deterministic_correctness: Literal[False]
    final_aesthetic_acceptance: Literal["human"]


class StaticHumanoidEvidencePolicyRefV1(TypedDict):
    policy_schema: Literal["tracepixel.static-humanoid-evidence-policy.v1"]
    sha256: str


class StaticHumanoidRequestV1(TypedDict):
    """Digest-bound static-humanoid context delegated to one existing AssetRequestV1."""

    schema: Literal["tracepixel.static-humanoid-request.v1"]
    request_ref: str
    request_schema: Literal["tracepixel.asset-request.v1"]
    request_sha256: str
    profile_ref: HumanoidProfileRefV1
    pose_ref: HumanoidPoseRefV1
    evidence_policy_ref: StaticHumanoidEvidencePolicyRefV1
