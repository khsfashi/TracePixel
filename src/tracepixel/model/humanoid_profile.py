from __future__ import annotations

from typing import Literal, TypedDict

HUMANOID_PROFILE_SCHEMA_V1 = "tracepixel.humanoid-profile.v1"

MAX_HUMANOID_PROFILE_SOURCES_V1 = 8
MAX_HUMANOID_PROFILE_FACTS_V1 = 64
MAX_HUMANOID_PROFILE_UNKNOWNS_V1 = 32
MAX_HUMANOID_LANDMARKS_V1 = 64
MAX_HUMANOID_PROPORTIONS_V1 = 64
MAX_HUMANOID_IDENTITY_FEATURES_V1 = 64
MAX_HUMANOID_EQUIPMENT_ANCHORS_V1 = 16

ConfidenceV1 = Literal["low", "medium", "high"]
ConstraintModeV1 = Literal["required-range", "hint", "stylization-tolerance"]
HumanoidSideV1 = Literal["center", "left", "right"]
HumanoidIdentityFeatureKindV1 = Literal["head-face-hair", "silhouette-critical"]
HumanoidCategoryStatusV1 = Literal["constrained", "unknown"]

HUMANOID_REQUIRED_CATEGORIES_V1 = (
    "character-family-or-archetype-identity",
    "canonical-body-landmarks",
    "bounded-relative-proportion-ranges",
    "symmetry-and-declared-asymmetry",
    "limb-and-joint-relationships",
    "head-face-hair-identity-features",
    "silhouette-critical-identity-features",
    "support-contact-expectations",
    "resolution-and-stylization-tolerances",
    "equipment-anchor-definitions",
    "provenance-evidence-references",
    "confidence-and-unknowns",
)


class HumanoidProfileRefV1(TypedDict):
    profile_id: str
    profile_schema: Literal["tracepixel.humanoid-profile.v1"]
    sha256: str


class HumanoidSourceEvidenceV1(TypedDict):
    source_id: str
    kind: str
    locator: str
    title: str
    retrieved_at_utc: str


class HumanoidObservedFactV1(TypedDict):
    fact_id: str
    text: str
    source_ids: list[str]


class HumanoidUnknownV1(TypedDict):
    unknown_id: str
    text: str


class HumanoidIdentityV1(TypedDict):
    family_id: str
    archetype_id: str
    form_id: str


class HumanoidLandmarkV1(TypedDict):
    landmark_id: str
    label: str
    parent_landmark_id: str | None
    mirror_landmark_id: str | None
    side: HumanoidSideV1


class HumanoidCategoryDeclarationV1(TypedDict):
    category: str
    status: HumanoidCategoryStatusV1
    rationale: str
    unknown_id: str | None


class HumanoidProportionRangeV1(TypedDict):
    minimum: float
    maximum: float


class HumanoidProportionConstraintV1(TypedDict):
    constraint_id: str
    mode: ConstraintModeV1
    landmark_ids: list[str]
    ratio_range: HumanoidProportionRangeV1
    text: str
    basis_fact_ids: list[str]
    confidence: ConfidenceV1


class HumanoidIdentityFeatureV1(TypedDict):
    feature_id: str
    kind: HumanoidIdentityFeatureKindV1
    landmark_ids: list[str]
    text: str
    basis_fact_ids: list[str]
    confidence: ConfidenceV1


class HumanoidEquipmentAnchorV1(TypedDict):
    anchor_id: str
    landmark_id: str
    side: HumanoidSideV1
    attachment_class: str
    basis_fact_ids: list[str]
    confidence: ConfidenceV1


class HumanoidStylizationToleranceV1(TypedDict):
    minimum_feature_pixels: int
    maximum_exaggeration_pixels: int
    basis_fact_ids: list[str]
    confidence: ConfidenceV1


class HumanoidProfileV1(TypedDict):
    """Provider-neutral static humanoid structure; never pixel/raster authority."""

    schema: Literal["tracepixel.humanoid-profile.v1"]
    profile_id: str
    subject_label: str
    identity: HumanoidIdentityV1
    source_evidence: list[HumanoidSourceEvidenceV1]
    observed_facts: list[HumanoidObservedFactV1]
    unknowns: list[HumanoidUnknownV1]
    landmarks: list[HumanoidLandmarkV1]
    category_declarations: list[HumanoidCategoryDeclarationV1]
    proportion_constraints: list[HumanoidProportionConstraintV1]
    identity_features: list[HumanoidIdentityFeatureV1]
    support_landmark_ids: list[str]
    equipment_anchors: list[HumanoidEquipmentAnchorV1]
    stylization_tolerance: HumanoidStylizationToleranceV1
