from __future__ import annotations

from copy import deepcopy
import unittest

from tracepixel.model.asset_set_schedule import (
    ASSET_REQUEST_SCHEMA_V1,
    ASSET_SET_REQUEST_SCHEMA_V1,
)
from tracepixel.model.asset_set_schedule_validation import (
    AssetSetScheduleValidationError,
    asset_request_sha256,
    asset_set_sha256,
    build_asset_set_schedule,
    validate_asset_request,
    validate_asset_set_request_payloads,
    validate_asset_set_schedule,
)

_STYLE = {
    "kind": "style",
    "profile_id": "small-rpg-icons",
    "profile_schema": "tracepixel.style-profile.v1",
    "sha256": "1" * 64,
}
_MORPHOLOGY = {
    "kind": "morphology",
    "profile_id": "leaf-form",
    "profile_schema": "tracepixel.morphology-profile.v1",
    "sha256": "2" * 64,
}


def _asset_set() -> dict[str, object]:
    return {
        "schema": "tracepixel.asset-set.v1",
        "asset_set_id": "starter-icons",
        "shared_profiles": [deepcopy(_STYLE), deepcopy(_MORPHOLOGY)],
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


def _art_intent() -> dict[str, object]:
    return {
        "schema": "tracepixel.art-intent.v1",
        "asset_class": "item-icon",
        "canvas": {"width": 16, "height": 16},
        "composition": {
            "occupied_bounds": {"x": 3, "y": 2, "width": 10, "height": 12},
            "facing": "front",
            "symmetry": {"axis": "vertical", "strength": "hint"},
            "light_direction": "top_left",
            "palette_budget": 8,
        },
    }


def _asset_request(instruction: str, *, morphology: bool = False) -> dict[str, object]:
    refs = [deepcopy(_STYLE)]
    if morphology:
        refs.append(deepcopy(_MORPHOLOGY))
    return {
        "schema": ASSET_REQUEST_SCHEMA_V1,
        "instruction": instruction,
        "art_intent": _art_intent(),
        "profile_refs": refs,
    }


def _payloads() -> dict[str, object]:
    return {
        "requests/potion-red.json": _asset_request("Create a red healing potion icon."),
        "requests/potion-blue.json": _asset_request("Create a blue mana potion icon."),
        "requests/leaf-green.json": _asset_request("Create a green leaf item icon.", morphology=True),
    }


def _request_set(asset_set: dict[str, object], payloads: dict[str, object]) -> dict[str, object]:
    shared = asset_set["shared_profiles"]
    assert type(shared) is list
    members = asset_set["members"]
    assert type(members) is list
    return {
        "schema": ASSET_SET_REQUEST_SCHEMA_V1,
        "asset_set_id": asset_set["asset_set_id"],
        "asset_set_sha256": asset_set_sha256(asset_set),
        "members": [
            {
                "member_id": member["member_id"],
                "request_ref": member["request_ref"],
                "request_sha256": asset_request_sha256(
                    payloads[member["request_ref"]],
                    shared_profiles=shared,
                ),
            }
            for member in members
        ],
    }


class AssetSetScheduleTests(unittest.TestCase):
    def test_manifest_and_schedule_preserve_declared_member_order(self) -> None:
        asset_set = _asset_set()
        payloads = _payloads()
        request_set = _request_set(asset_set, payloads)
        self.assertIs(
            request_set,
            validate_asset_set_request_payloads(request_set, asset_set, payloads),
        )

        schedule = build_asset_set_schedule(request_set, asset_set, payloads)
        self.assertEqual([0, 1, 2], [member["ordinal"] for member in schedule["members"]])
        self.assertEqual(
            ["potion-red", "potion-blue", "leaf-green"],
            [member["member_id"] for member in schedule["members"]],
        )
        self.assertEqual("declared-order-bounded-concurrency", schedule["dispatch_policy"])
        self.assertEqual(2, schedule["max_concurrency"])

    def test_instruction_is_part_of_effective_request_identity(self) -> None:
        red = _asset_request("Create a red healing potion icon.")
        blue = _asset_request("Create a blue mana potion icon.")
        self.assertEqual(red["art_intent"], blue["art_intent"])
        self.assertNotEqual(asset_request_sha256(red), asset_request_sha256(blue))

    def test_asset_request_is_closed_and_reuses_existing_art_intent_validator(self) -> None:
        request = _asset_request("Create a red healing potion icon.")
        request["pixels"] = []
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "invalid_fields"):
            validate_asset_request(request)

        request = _asset_request("Create a red healing potion icon.")
        art_intent = request["art_intent"]
        assert type(art_intent) is dict
        art_intent["canvas"] = {"width": 0, "height": 16}
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "invalid_art_intent"):
            validate_asset_request(request)

    def test_member_profile_refs_must_be_exact_shared_digest_pins(self) -> None:
        asset_set = _asset_set()
        request = _asset_request("Create a red healing potion icon.")
        refs = request["profile_refs"]
        assert type(refs) is list and type(refs[0]) is dict
        refs[0]["sha256"] = "3" * 64
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "unshared_profile"):
            validate_asset_request(request, shared_profiles=asset_set["shared_profiles"])

    def test_manifest_refuses_member_reordering_or_ref_substitution(self) -> None:
        asset_set = _asset_set()
        payloads = _payloads()
        request_set = _request_set(asset_set, payloads)
        members = request_set["members"]
        assert type(members) is list
        members[0], members[1] = members[1], members[0]
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "member_order_mismatch"):
            validate_asset_set_request_payloads(request_set, asset_set, payloads)

        request_set = _request_set(asset_set, payloads)
        members = request_set["members"]
        assert type(members) is list and type(members[0]) is dict
        members[0]["request_ref"] = "requests/other.json"
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "request_ref_mismatch"):
            validate_asset_set_request_payloads(request_set, asset_set, payloads)

    def test_payload_map_must_be_exact_and_member_payload_is_digest_bound(self) -> None:
        asset_set = _asset_set()
        payloads = _payloads()
        request_set = _request_set(asset_set, payloads)

        missing = dict(payloads)
        del missing["requests/potion-blue.json"]
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "payload_set_mismatch"):
            validate_asset_set_request_payloads(request_set, asset_set, missing)

        changed = deepcopy(payloads)
        blue = changed["requests/potion-blue.json"]
        assert type(blue) is dict
        blue["instruction"] = "Create a purple potion icon."
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "request_digest_mismatch"):
            validate_asset_set_request_payloads(request_set, asset_set, changed)

    def test_schedule_is_deterministic_and_contains_no_runtime_result_state(self) -> None:
        asset_set = _asset_set()
        payloads = _payloads()
        request_set = _request_set(asset_set, payloads)
        first = build_asset_set_schedule(request_set, asset_set, payloads)
        second = build_asset_set_schedule(deepcopy(request_set), deepcopy(asset_set), deepcopy(payloads))
        self.assertEqual(first, second)

        tampered = deepcopy(first)
        tampered["status"] = "running"
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "invalid_fields"):
            validate_asset_set_schedule(tampered, request_set, asset_set, payloads)

    def test_schedule_tampering_is_rejected(self) -> None:
        asset_set = _asset_set()
        payloads = _payloads()
        request_set = _request_set(asset_set, payloads)
        schedule = build_asset_set_schedule(request_set, asset_set, payloads)

        members = schedule["members"]
        assert type(members) is list and type(members[0]) is dict
        members[0]["ordinal"] = 1
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "schedule_mismatch"):
            validate_asset_set_schedule(schedule, request_set, asset_set, payloads)

        schedule = build_asset_set_schedule(request_set, asset_set, payloads)
        schedule["max_concurrency"] = 1
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "schedule_mismatch"):
            validate_asset_set_schedule(schedule, request_set, asset_set, payloads)

    def test_schedule_rejects_bool_for_integer_fields_even_when_bool_compares_equal(self) -> None:
        asset_set = _asset_set()
        execution = asset_set["execution"]
        assert type(execution) is dict
        execution["max_concurrency"] = 1
        payloads = _payloads()
        request_set = _request_set(asset_set, payloads)
        schedule = build_asset_set_schedule(request_set, asset_set, payloads)
        schedule["max_concurrency"] = True
        with self.assertRaisesRegex(AssetSetScheduleValidationError, "invalid_type"):
            validate_asset_set_schedule(schedule, request_set, asset_set, payloads)


if __name__ == "__main__":
    unittest.main()
