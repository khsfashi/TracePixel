from __future__ import annotations

from typing import Literal, TypedDict

from .art_intent import ArtIntentV1
from .asset_set import AssetSetAggregateBudgetV1, AssetSetProfileRefV1

ASSET_REQUEST_SCHEMA_V1 = "tracepixel.asset-request.v1"
ASSET_SET_REQUEST_SCHEMA_V1 = "tracepixel.asset-set-request.v1"
ASSET_SET_SCHEDULE_SCHEMA_V1 = "tracepixel.asset-set-schedule.v1"
MAX_ASSET_REQUEST_INSTRUCTION_CHARS_V1 = 4096

DispatchPolicyV1 = Literal["declared-order-bounded-concurrency"]


class AssetRequestV1(TypedDict):
    """One single-asset authoring request consumed by the existing TracePixel path."""

    schema: Literal["tracepixel.asset-request.v1"]
    instruction: str
    art_intent: ArtIntentV1
    profile_refs: list[AssetSetProfileRefV1]


class AssetSetRequestMemberV1(TypedDict):
    """Digest binding from one AssetSet member identity to its immutable request payload."""

    member_id: str
    request_ref: str
    request_sha256: str


class AssetSetRequestV1(TypedDict):
    """Closed multi-asset request manifest; referenced requests remain independently cacheable."""

    schema: Literal["tracepixel.asset-set-request.v1"]
    asset_set_id: str
    asset_set_sha256: str
    members: list[AssetSetRequestMemberV1]


class AssetSetScheduledMemberV1(TypedDict):
    """Immutable dispatch queue entry. Runtime status/result state is intentionally excluded."""

    ordinal: int
    member_id: str
    request_ref: str
    request_sha256: str


class AssetSetScheduleV1(TypedDict):
    """Deterministic queue contract for later isolated member execution."""

    schema: Literal["tracepixel.asset-set-schedule.v1"]
    asset_set_id: str
    asset_set_sha256: str
    request_sha256: str
    member_authority: Literal["single-asset-pipeline"]
    ordering: Literal["declared-member-order"]
    dispatch_policy: DispatchPolicyV1
    failure_policy: Literal["isolate-member"]
    max_concurrency: int
    aggregate_budget: AssetSetAggregateBudgetV1
    members: list[AssetSetScheduledMemberV1]
