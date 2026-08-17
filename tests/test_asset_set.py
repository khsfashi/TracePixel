from __future__ import annotations

from copy import deepcopy
import unittest

from tracepixel.model.asset_set import ASSET_SET_SCHEMA_V1, MAX_ASSET_SET_MEMBERS_V1
from tracepixel.model.asset_set_validation import AssetSetValidationError, validate_asset_set


def _asset_set() -> dict[str, object]:
    return {
        "schema": ASSET_SET_SCHEMA_V1,
        "asset_set_id": "starter-icons",
        "shared_profiles": [
            {
                "kind": "style",
                "profile_id": "small-rpg-icons",
                "profile_schema": "tracepixel.style-profile.v1",
                "sha256": "1" * 64,
            },
            {
                "kind": "morphology",
                "profile_id": "leaf-form",
                "profile_schema": "tracepixel.morphology-profile.v1",
                "sha256": "2" * 64,
            },
        ],
        "members": [
            {"member_id": "potion-red", "request_ref": "requests/potion-red.json"},
            {"member_id": "potion-blue", "request_ref": "requests/potion-blue.json"},
            {"member_id": "leaf-green", "request_ref": "requests/leaf-green.json"},
        ],
        "execution": {
            "member_authority": "single-asset-pipeline",
            "ordering": "declared-member-order",
            "failure_policy": "isolate-member",
            "max_concurrency": 2,
            "aggregate_budget": {
                "max_provider_calls": 24,
                "max_pixel_edits": 6144,
                "max_wall_time_ms": 3_600_000,
            },
        },
    }


class AssetSetValidationTests(unittest.TestCase):
    def test_valid_asset_set_is_returned_without_copy_or_reordering(self) -> None:
        asset_set = _asset_set()
        result = validate_asset_set(asset_set)
        self.assertIs(asset_set, result)
        self.assertEqual(["potion-red", "potion-blue", "leaf-green"], [m["member_id"] for m in result["members"]])

    def test_contract_is_closed_and_cannot_embed_raster_authority(self) -> None:
        for field in ("rgba", "canvas", "pixel_program", "outputs"):
            asset_set = _asset_set()
            asset_set[field] = object()
            with self.assertRaisesRegex(AssetSetValidationError, "invalid_fields"):
                validate_asset_set(asset_set)

    def test_member_ids_are_unique_and_declared_order_is_authoritative(self) -> None:
        asset_set = _asset_set()
        members = asset_set["members"]
        assert type(members) is list
        members[1]["member_id"] = "potion-red"
        with self.assertRaisesRegex(AssetSetValidationError, "duplicate_member"):
            validate_asset_set(asset_set)

        asset_set = _asset_set()
        execution = asset_set["execution"]
        assert type(execution) is dict
        execution["ordering"] = "completion-order"
        with self.assertRaisesRegex(AssetSetValidationError, "invalid_ordering"):
            validate_asset_set(asset_set)

    def test_batch_execution_must_reuse_single_asset_path_and_isolate_failures(self) -> None:
        for key, value, code in (
            ("member_authority", "batch-raster", "invalid_member_authority"),
            ("failure_policy", "abort-all", "invalid_failure_policy"),
        ):
            asset_set = _asset_set()
            execution = asset_set["execution"]
            assert type(execution) is dict
            execution[key] = value
            with self.assertRaisesRegex(AssetSetValidationError, code):
                validate_asset_set(asset_set)

    def test_concurrency_is_explicit_bounded_and_not_bool(self) -> None:
        for value in (0, 4, True):
            asset_set = _asset_set()
            execution = asset_set["execution"]
            assert type(execution) is dict
            execution["max_concurrency"] = value
            with self.assertRaises(AssetSetValidationError):
                validate_asset_set(asset_set)

    def test_aggregate_budgets_are_finite_positive_exact_integers(self) -> None:
        for field in ("max_provider_calls", "max_pixel_edits", "max_wall_time_ms"):
            for value in (0, True, -1):
                asset_set = _asset_set()
                execution = asset_set["execution"]
                assert type(execution) is dict
                budget = execution["aggregate_budget"]
                assert type(budget) is dict
                budget[field] = value
                with self.assertRaises(AssetSetValidationError):
                    validate_asset_set(asset_set)

    def test_shared_profiles_are_digest_pinned_and_duplicate_identity_is_rejected(self) -> None:
        asset_set = _asset_set()
        profiles = asset_set["shared_profiles"]
        assert type(profiles) is list
        profiles[0]["sha256"] = "ABC"
        with self.assertRaisesRegex(AssetSetValidationError, "invalid_digest"):
            validate_asset_set(asset_set)

        asset_set = _asset_set()
        profiles = asset_set["shared_profiles"]
        assert type(profiles) is list
        profiles.append(deepcopy(profiles[0]))
        with self.assertRaisesRegex(AssetSetValidationError, "duplicate_profile"):
            validate_asset_set(asset_set)

    def test_member_count_is_bounded(self) -> None:
        asset_set = _asset_set()
        asset_set["members"] = [
            {"member_id": f"m{index}", "request_ref": f"requests/{index}.json"}
            for index in range(MAX_ASSET_SET_MEMBERS_V1 + 1)
        ]
        execution = asset_set["execution"]
        assert type(execution) is dict
        execution["max_concurrency"] = 1
        with self.assertRaisesRegex(AssetSetValidationError, "invalid_member_count"):
            validate_asset_set(asset_set)


if __name__ == "__main__":
    unittest.main()
