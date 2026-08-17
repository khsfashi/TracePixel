from __future__ import annotations

from typing import Literal, TypedDict

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
