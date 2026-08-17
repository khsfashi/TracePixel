from __future__ import annotations

from typing import Literal, TypedDict

ASSET_SET_SCHEMA_V1 = "tracepixel.asset-set.v1"
MAX_ASSET_SET_MEMBERS_V1 = 64
MAX_SHARED_PROFILES_V1 = 16
MAX_BATCH_CONCURRENCY_V1 = 8
MAX_AGGREGATE_PROVIDER_CALLS_V1 = 512
MAX_AGGREGATE_PIXEL_EDITS_V1 = 131_072
MAX_AGGREGATE_WALL_TIME_MS_V1 = 86_400_000

ProfileKindV1 = Literal["style", "palette", "morphology"]


class AssetSetProfileRefV1(TypedDict):
    """Immutable shared profile identity; profile semantics remain outside raster authority."""

    kind: ProfileKindV1
    profile_id: str
    profile_schema: str
    sha256: str


class AssetSetMemberV1(TypedDict):
    """One deterministically ordered member delegated to the existing single-asset path."""

    member_id: str
    request_ref: str


class AssetSetAggregateBudgetV1(TypedDict):
    max_provider_calls: int
    max_pixel_edits: int
    max_wall_time_ms: int


class AssetSetExecutionV1(TypedDict):
    member_authority: Literal["single-asset-pipeline"]
    ordering: Literal["declared-member-order"]
    failure_policy: Literal["isolate-member"]
    max_concurrency: int
    aggregate_budget: AssetSetAggregateBudgetV1


class AssetSetV1(TypedDict):
    """Versioned batch envelope that never becomes a second pixel/raster authority."""

    schema: Literal["tracepixel.asset-set.v1"]
    asset_set_id: str
    shared_profiles: list[AssetSetProfileRefV1]
    members: list[AssetSetMemberV1]
    execution: AssetSetExecutionV1
