from __future__ import annotations

from copy import deepcopy
import unittest

from tracepixel.model.asset_set_consistency_validation import (
    AssetSetConsistencyValidationError,
    build_asset_set_consistency,
    validate_asset_set_consistency,
)
from tracepixel.model.asset_set_schedule_validation import asset_request_sha256, asset_set_sha256


STYLE = {
    "kind": "style",
    "profile_id": "small-rpg-icons",
    "profile_schema": "tracepixel.style-profile.v1",
    "sha256": "1" * 64,
}
ALT_STYLE = {
    "kind": "style",
    "profile_id": "alternate-icons",
    "profile_schema": "tracepixel.style-profile.v1",
    "sha256": "3" * 64,
}
PALETTE = {
    "kind": "palette",
    "profile_id": "starter-palette",
    "profile_schema": "tracepixel.palette-profile.v1",
    "sha256": "4" * 64,
}
MORPHOLOGY = {
    "kind": "morphology",
    "profile_id": "leaf-form",
    "profile_schema": "tracepixel.morphology-profile.v1",
    "sha256": "2" * 64,
}


def _asset_set(*, extra_profiles: list[dict[str, object]] | None = None) -> dict[str, object]:
    profiles = [deepcopy(STYLE), deepcopy(MORPHOLOGY)]
    if extra_profiles:
        profiles.extend(deepcopy(extra_profiles))
    return {
        "schema": "tracepixel.asset-set.v1",
        "asset_set_id": "starter-icons",
        "shared_profiles": profiles,
        "members": [
            {"member_id": "potion", "request_ref": "requests/potion.json"},
            {"member_id": "leaf", "request_ref": "requests/leaf.json"},
        ],
        "execution": {
            "member_authority": "single-asset-pipeline",
            "ordering": "declared-member-order",
            "failure_policy": "isolate-member",
            "max_concurrency": 2,
            "aggregate_budget": {
                "max_provider_calls": 16,
                "max_pixel_edits": 4096,
                "max_wall_time_ms": 60_000,
            },
        },
    }


def _request(profile_refs: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "tracepixel.asset-request.v1",
        "instruction": "Create one small item icon.",
        "art_intent": {
            "schema": "tracepixel.art-intent.v1",
            "asset_class": "item-icon",
            "canvas": {"width": 16, "height": 16},
            "composition": {
                "occupied_bounds": {"x": 2, "y": 2, "width": 12, "height": 12},
                "facing": "front",
                "symmetry": None,
                "light_direction": "top_left",
                "palette_budget": 8,
            },
        },
        "profile_refs": deepcopy(profile_refs),
    }


def _payloads(
    *,
    potion_refs: list[dict[str, object]] | None = None,
    leaf_refs: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "requests/potion.json": _request(potion_refs if potion_refs is not None else [STYLE]),
        "requests/leaf.json": _request(leaf_refs if leaf_refs is not None else [STYLE, MORPHOLOGY]),
    }


def _bind(asset_set: dict[str, object], payloads: dict[str, object]) -> dict[str, object]:
    shared = asset_set["shared_profiles"]
    members = asset_set["members"]
    assert type(members) is list
    return {
        "schema": "tracepixel.asset-set-request.v1",
        "asset_set_id": asset_set["asset_set_id"],
        "asset_set_sha256": asset_set_sha256(asset_set),
        "members": [
            {
                "member_id": member["member_id"],
                "request_ref": member["request_ref"],
                "request_sha256": asset_request_sha256(payloads[member["request_ref"]], shared_profiles=shared),
            }
            for member in members
        ],
    }


class AssetSetConsistencyTests(unittest.TestCase):
    def test_builds_exact_style_binding_and_keeps_visual_claims_perceptual(self) -> None:
        asset_set = _asset_set()
        payloads = _payloads()
        request_set = _bind(asset_set, payloads)

        contract = build_asset_set_consistency(request_set, asset_set, payloads)

        self.assertEqual(STYLE, contract["style_profile"])
        self.assertIsNone(contract["palette_profile"])
        self.assertEqual("exact-digest-request-binding", contract["profile_binding_policy"])
        self.assertEqual("perceptual-evidence-required", contract["visual_style_policy"])
        self.assertEqual("perceptual-evidence-required", contract["visual_palette_policy"])
        self.assertEqual(["potion", "leaf"], [member["member_id"] for member in contract["members"]])
        self.assertEqual([STYLE, MORPHOLOGY], contract["members"][1]["profile_refs"])

    def test_shared_palette_profile_must_cover_every_member(self) -> None:
        asset_set = _asset_set(extra_profiles=[PALETTE])
        payloads = _payloads(potion_refs=[STYLE, PALETTE], leaf_refs=[STYLE, PALETTE, MORPHOLOGY])
        request_set = _bind(asset_set, payloads)

        contract = build_asset_set_consistency(request_set, asset_set, payloads)
        self.assertEqual(PALETTE, contract["palette_profile"])

        partial = _payloads(potion_refs=[STYLE, PALETTE], leaf_refs=[STYLE, MORPHOLOGY])
        partial_request_set = _bind(asset_set, partial)
        with self.assertRaisesRegex(AssetSetConsistencyValidationError, "partial_palette_profile"):
            build_asset_set_consistency(partial_request_set, asset_set, partial)

    def test_every_member_must_share_one_exact_style_profile(self) -> None:
        asset_set = _asset_set(extra_profiles=[ALT_STYLE])
        mismatched = _payloads(potion_refs=[STYLE], leaf_refs=[ALT_STYLE, MORPHOLOGY])
        request_set = _bind(asset_set, mismatched)
        with self.assertRaisesRegex(AssetSetConsistencyValidationError, "style_profile_mismatch"):
            build_asset_set_consistency(request_set, asset_set, mismatched)

        missing = _payloads(potion_refs=[], leaf_refs=[STYLE, MORPHOLOGY])
        missing_request_set = _bind(asset_set, missing)
        with self.assertRaisesRegex(AssetSetConsistencyValidationError, "style_profile_cardinality"):
            build_asset_set_consistency(missing_request_set, asset_set, missing)

    def test_consistency_contract_is_closed_and_tamper_evident(self) -> None:
        asset_set = _asset_set()
        payloads = _payloads()
        request_set = _bind(asset_set, payloads)
        contract = build_asset_set_consistency(request_set, asset_set, payloads)
        self.assertIs(contract, validate_asset_set_consistency(contract, request_set, asset_set, payloads))

        tampered = deepcopy(contract)
        tampered["visual_style_policy"] = "deterministic-pass"
        with self.assertRaisesRegex(AssetSetConsistencyValidationError, "consistency_contract_mismatch"):
            validate_asset_set_consistency(tampered, request_set, asset_set, payloads)

        extra = deepcopy(contract)
        extra["style_score"] = 1.0
        with self.assertRaisesRegex(AssetSetConsistencyValidationError, "invalid_fields"):
            validate_asset_set_consistency(extra, request_set, asset_set, payloads)


if __name__ == "__main__":
    unittest.main()
