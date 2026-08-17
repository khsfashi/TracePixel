from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from .asset_set import AssetSetProfileRefV1, AssetSetV1
from .asset_set_consistency import ASSET_SET_CONSISTENCY_SCHEMA_V1, AssetSetConsistencyV1
from .asset_set_schedule import AssetRequestV1, AssetSetRequestV1
from .asset_set_schedule_validation import (
    AssetSetScheduleValidationError,
    asset_set_request_sha256,
    asset_set_sha256,
    validate_asset_set_request_payloads,
)


_CONSISTENCY_FIELDS = frozenset(
    (
        "schema",
        "asset_set_id",
        "asset_set_sha256",
        "request_sha256",
        "profile_binding_policy",
        "style_profile",
        "palette_profile",
        "visual_style_policy",
        "visual_palette_policy",
        "members",
    )
)


class AssetSetConsistencyValidationError(ValueError):
    """Deterministic P8-B2 consistency-contract rejection with stable code/path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise AssetSetConsistencyValidationError(code, path, message)


def _profile_key(ref: Mapping[str, object]) -> tuple[object, object, object, object]:
    return (ref.get("kind"), ref.get("profile_id"), ref.get("profile_schema"), ref.get("sha256"))


def _copy_profile(ref: Mapping[str, object]) -> AssetSetProfileRefV1:
    return cast(
        AssetSetProfileRefV1,
        {
            "kind": ref["kind"],
            "profile_id": ref["profile_id"],
            "profile_schema": ref["profile_schema"],
            "sha256": ref["sha256"],
        },
    )


def _refs_of_kind(request: AssetRequestV1, kind: str) -> list[AssetSetProfileRefV1]:
    return [ref for ref in request["profile_refs"] if ref["kind"] == kind]


def build_asset_set_consistency(
    request_set: object,
    asset_set: object,
    request_payloads: Mapping[str, object],
) -> AssetSetConsistencyV1:
    """Derive a closed consistency policy without provider calls or raster authority."""

    try:
        validated_request_set = validate_asset_set_request_payloads(request_set, asset_set, request_payloads)
        set_digest = asset_set_sha256(asset_set)
        request_digest = asset_set_request_sha256(request_set, asset_set, request_payloads)
    except AssetSetScheduleValidationError as exc:
        _fail("invalid_inputs", f"$context{exc.path[1:]}", f"{exc.code}: {exc.message}")

    validated_set = cast(AssetSetV1, asset_set)
    validated_manifest = cast(AssetSetRequestV1, validated_request_set)
    style_profile: AssetSetProfileRefV1 | None = None
    palette_profile: AssetSetProfileRefV1 | None = None
    palette_presence = 0
    members: list[dict[str, object]] = []

    for ordinal, manifest_member in enumerate(validated_manifest["members"]):
        request_ref = manifest_member["request_ref"]
        request = cast(AssetRequestV1, request_payloads[request_ref])
        styles = _refs_of_kind(request, "style")
        if len(styles) != 1:
            _fail(
                "style_profile_cardinality",
                f"$context.request_payloads[{request_ref!r}].profile_refs",
                "every AssetSet member must bind exactly one shared style profile",
            )
        if style_profile is None:
            style_profile = _copy_profile(styles[0])
        elif _profile_key(styles[0]) != _profile_key(style_profile):
            _fail(
                "style_profile_mismatch",
                f"$context.request_payloads[{request_ref!r}].profile_refs",
                "all AssetSet members must bind the same exact digest-pinned style profile",
            )

        palettes = _refs_of_kind(request, "palette")
        if len(palettes) > 1:
            _fail(
                "palette_profile_cardinality",
                f"$context.request_payloads[{request_ref!r}].profile_refs",
                "a member may bind at most one shared palette profile",
            )
        if palettes:
            palette_presence += 1
            if palette_profile is None:
                palette_profile = _copy_profile(palettes[0])
            elif _profile_key(palettes[0]) != _profile_key(palette_profile):
                _fail(
                    "palette_profile_mismatch",
                    f"$context.request_payloads[{request_ref!r}].profile_refs",
                    "palette-profile binding must be identical across the whole AssetSet",
                )

        members.append(
            {
                "ordinal": ordinal,
                "member_id": manifest_member["member_id"],
                "request_sha256": manifest_member["request_sha256"],
                "profile_refs": [_copy_profile(ref) for ref in request["profile_refs"]],
            }
        )

    if palette_presence not in (0, len(validated_manifest["members"])):
        _fail(
            "partial_palette_profile",
            "$context.request_payloads",
            "a shared palette profile must bind every member or no member",
        )
    if style_profile is None:
        _fail("missing_style_profile", "$context.request_payloads", "style profile could not be resolved")

    return cast(
        AssetSetConsistencyV1,
        {
            "schema": ASSET_SET_CONSISTENCY_SCHEMA_V1,
            "asset_set_id": validated_set["asset_set_id"],
            "asset_set_sha256": set_digest,
            "request_sha256": request_digest,
            "profile_binding_policy": "exact-digest-request-binding",
            "style_profile": style_profile,
            "palette_profile": palette_profile,
            "visual_style_policy": "perceptual-evidence-required",
            "visual_palette_policy": "perceptual-evidence-required",
            "members": members,
        },
    )


def validate_asset_set_consistency(
    consistency: object,
    request_set: object,
    asset_set: object,
    request_payloads: Mapping[str, object],
) -> AssetSetConsistencyV1:
    """Require the contract to be the exact deterministic projection of frozen inputs."""

    expected = build_asset_set_consistency(request_set, asset_set, request_payloads)
    if type(consistency) is not dict:
        _fail("invalid_type", "$", "must be a JSON object")
    root = cast(dict[object, object], consistency)
    if not all(type(key) is str for key in root):
        _fail("invalid_fields", "$", "object keys must be strings")
    typed = cast(dict[str, object], root)
    actual_fields = frozenset(typed)
    if actual_fields != _CONSISTENCY_FIELDS:
        _fail("invalid_fields", "$", "must contain only the closed P8-B2 consistency fields")
    if typed["schema"] != ASSET_SET_CONSISTENCY_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {ASSET_SET_CONSISTENCY_SCHEMA_V1!r}")
    if typed != expected:
        _fail(
            "consistency_contract_mismatch",
            "$",
            "must equal the deterministic consistency projection of the frozen AssetSet requests",
        )
    return cast(AssetSetConsistencyV1, consistency)
