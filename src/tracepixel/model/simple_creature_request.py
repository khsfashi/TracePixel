from __future__ import annotations

from typing import Literal, TypedDict

from .creature_pose import CreaturePoseRefV1
from .research_profile import MorphologyProfileRefV1

SIMPLE_CREATURE_REQUEST_SCHEMA_V1 = "tracepixel.simple-creature-request.v1"
SIMPLE_CREATURE_EVIDENCE_POLICY_SCHEMA_V1 = "tracepixel.simple-creature-evidence-policy.v1"

DETERMINISTIC_EVIDENCE_FACTS_V1 = (
    "schema-and-version-identity",
    "digest-binding",
    "finite-range-validity",
    "landmark-reference-integrity",
    "declared-required-relation-satisfaction-when-structured",
    "support-contact-declarations",
    "existing-raster-and-qa-facts",
    "provider-cost-and-provenance-accounting",
)

PERCEPTUAL_EVIDENCE_FACTS_V1 = (
    "species-or-form-recognizability",
    "silhouette-readability",
    "stylized-anatomy-believability",
    "pose-intent-readability",
    "visual-identity-and-style-coherence",
)


class SimpleCreatureEvidencePolicyV1(TypedDict):
    """Frozen C3 authority split. Perceptual facts never become deterministic correctness."""

    schema: Literal["tracepixel.simple-creature-evidence-policy.v1"]
    deterministic_facts: list[str]
    perceptual_facts: list[str]
    vlm_is_deterministic_correctness: Literal[False]
    final_aesthetic_acceptance: Literal["human"]


class SimpleCreatureEvidencePolicyRefV1(TypedDict):
    policy_schema: Literal["tracepixel.simple-creature-evidence-policy.v1"]
    sha256: str


class SimpleCreatureRequestV1(TypedDict):
    """Digest-bound creature context layered over, and delegated to, one existing AssetRequestV1."""

    schema: Literal["tracepixel.simple-creature-request.v1"]
    request_ref: str
    request_schema: Literal["tracepixel.asset-request.v1"]
    request_sha256: str
    morphology_ref: MorphologyProfileRefV1
    pose_ref: CreaturePoseRefV1
    evidence_policy_ref: SimpleCreatureEvidencePolicyRefV1
