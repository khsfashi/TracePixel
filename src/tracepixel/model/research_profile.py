from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

FORM_RESOLUTION_SCHEMA_V1 = "tracepixel.form-resolution.v1"
MORPHOLOGY_PROFILE_SCHEMA_V1 = "tracepixel.morphology-profile.v1"

MAX_RESEARCH_SOURCE_KINDS_V1 = 6
MAX_RESEARCH_SOURCES_V1 = 8
MAX_RESEARCH_SEARCH_CALLS_V1 = 8
MAX_RESEARCH_FETCH_CALLS_V1 = 16
MAX_RESEARCH_WALL_TIME_MS_V1 = 600_000
MAX_PROFILE_FACTS_V1 = 64
MAX_PROFILE_CONSTRAINTS_V1 = 64
MAX_PROFILE_CONVENTIONS_V1 = 32
MAX_PROFILE_UNKNOWNS_V1 = 32
MAX_PROFILE_LANDMARKS_V1 = 64
MAX_PROFILE_STRUCTURAL_CONSTRAINTS_V1 = 96
MAX_PROFILE_CATEGORY_DECLARATIONS_V1 = 6

SourceKindV1 = Literal[
    "official",
    "academic",
    "museum",
    "encyclopedic",
    "manufacturer",
    "general_web",
]
ResearchResolutionKindV1 = Literal["known_profile", "research_required"]
ConfidenceV1 = Literal["low", "medium", "high"]
ConstraintModeV1 = Literal["required-range", "hint", "stylization-tolerance"]
CreatureConstraintCategoryV1 = Literal[
    "relative-proportion",
    "symmetry-orientation",
    "articulation",
    "silhouette-critical",
    "support-contact",
    "resolution-stylization",
]
CreatureConstraintStatusV1 = Literal["constrained", "not-applicable", "unknown"]
RangeUnitV1 = Literal["ratio", "degrees", "pixels"]


class MorphologyProfileRefV1(TypedDict):
    profile_id: str
    profile_schema: Literal["tracepixel.morphology-profile.v1"]
    sha256: str


class ResearchBudgetV1(TypedDict):
    max_sources: int
    max_search_calls: int
    max_fetch_calls: int
    max_wall_time_ms: int


class ResearchRequestV1(TypedDict):
    goal: str
    allowed_source_kinds: list[SourceKindV1]
    budget: ResearchBudgetV1


class FormResolutionV1(TypedDict):
    """Resolve a requested form to a frozen profile or an explicit bounded research request."""

    schema: Literal["tracepixel.form-resolution.v1"]
    form_id: str
    resolution: ResearchResolutionKindV1
    profile_ref: MorphologyProfileRefV1 | None
    research_request: ResearchRequestV1 | None


class SourceEvidenceV1(TypedDict):
    """Source identity only; source bodies/images never become canonical asset data here."""

    source_id: str
    kind: SourceKindV1
    locator: str
    title: str
    retrieved_at_utc: str


class ObservedFactV1(TypedDict):
    fact_id: str
    text: str
    source_ids: list[str]


class InferredConstraintV1(TypedDict):
    constraint_id: str
    text: str
    basis_fact_ids: list[str]
    confidence: ConfidenceV1


class ArtisticConventionV1(TypedDict):
    convention_id: str
    text: str


class UnknownV1(TypedDict):
    unknown_id: str
    text: str


class MorphologySubjectV1(TypedDict):
    family_id: str
    species_id: str
    form_id: str


class MorphologyLandmarkV1(TypedDict):
    landmark_id: str
    label: str
    parent_landmark_id: str | None
    mirror_landmark_id: str | None


class MorphologyValueRangeV1(TypedDict):
    minimum: float
    maximum: float
    unit: RangeUnitV1


class MorphologyCategoryDeclarationV1(TypedDict):
    category: CreatureConstraintCategoryV1
    status: CreatureConstraintStatusV1
    rationale: str
    unknown_id: str | None


class MorphologyStructuralConstraintV1(TypedDict):
    constraint_id: str
    category: CreatureConstraintCategoryV1
    mode: ConstraintModeV1
    landmark_ids: list[str]
    value_range: MorphologyValueRangeV1 | None
    text: str
    basis_fact_ids: list[str]
    confidence: ConfidenceV1


class CreatureStructureV1(TypedDict):
    """Provider-neutral simple-creature structure; never pixel/raster authority."""

    subject: MorphologySubjectV1
    landmarks: list[MorphologyLandmarkV1]
    category_declarations: list[MorphologyCategoryDeclarationV1]
    constraints: list[MorphologyStructuralConstraintV1]


class MorphologyProfileV1(TypedDict):
    """Reusable research-backed form knowledge, separate from pixel/raster authority."""

    schema: Literal["tracepixel.morphology-profile.v1"]
    profile_id: str
    subject_label: str
    source_evidence: list[SourceEvidenceV1]
    observed_facts: list[ObservedFactV1]
    inferred_constraints: list[InferredConstraintV1]
    artistic_conventions: list[ArtisticConventionV1]
    unknowns: list[UnknownV1]
    creature_structure: NotRequired[CreatureStructureV1]
