from __future__ import annotations

from typing import Literal, TypedDict

from .asset_set import AssetSetProfileRefV1

ASSET_SET_CONSISTENCY_SCHEMA_V1 = "tracepixel.asset-set-consistency.v1"

ProfileBindingPolicyV1 = Literal["exact-digest-request-binding"]
VisualConsistencyPolicyV1 = Literal["perceptual-evidence-required"]


class AssetSetConsistencyMemberV1(TypedDict):
    ordinal: int
    member_id: str
    request_sha256: str
    profile_refs: list[AssetSetProfileRefV1]


class AssetSetConsistencyV1(TypedDict):
    """Immutable cross-asset consistency policy derived from frozen AssetSet requests."""

    schema: Literal["tracepixel.asset-set-consistency.v1"]
    asset_set_id: str
    asset_set_sha256: str
    request_sha256: str
    profile_binding_policy: ProfileBindingPolicyV1
    style_profile: AssetSetProfileRefV1
    palette_profile: AssetSetProfileRefV1 | None
    visual_style_policy: VisualConsistencyPolicyV1
    visual_palette_policy: VisualConsistencyPolicyV1
    members: list[AssetSetConsistencyMemberV1]
