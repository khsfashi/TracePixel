from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tracepixel.model.asset_set_schedule_validation import (
    asset_request_sha256,
    asset_set_request_sha256,
    asset_set_sha256,
    build_asset_set_schedule,
    validate_asset_set_request_payloads,
    validate_asset_set_schedule,
)
from tracepixel.model.asset_set_validation import validate_asset_set

ROOT = Path(__file__).resolve().parents[2]
ASSET_SET = ROOT / "evidence" / "p8_x0" / "reference-asset-set.v1.json"
REQUEST_SET = ROOT / "evidence" / "p8_b0" / "reference-asset-set-request.v1.json"
SCHEDULE = ROOT / "evidence" / "p8_b0" / "reference-asset-set-schedule.v1.json"
REQUEST_ROOT = ROOT / "evidence" / "p8_b0"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"
EXPECTED_ASSET_SET_SHA256 = "18f2ad6f36f1b6d53d81ef59963db763ee5f8870393f19bcdeb9c56627629f66"
EXPECTED_REQUEST_SHA256 = "63ca379357772a14f221996e1dc3cae73a5796fefa0282ebbc1c21712baf0faa"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _validate_lane(lane: dict[str, object]) -> None:
    if lane.get("current") != "P8" or lane.get("active_issue") != 92:
        raise SystemExit("P8-B0 checkpoint requires live P8 / issue #92")
    children = lane.get("child_sequences")
    if type(children) is not dict:
        raise SystemExit("core lane child_sequences malformed")
    p8 = cast(dict[str, object], children).get("P8")
    child = lane.get("current_child")
    if type(p8) is not list or child not in cast(list[object], p8):
        raise SystemExit("active P8 child is not declared")
    names = cast(list[str], p8)
    if "P8-B0" not in names or names.index(cast(str, child)) < names.index("P8-B0"):
        raise SystemExit("core lane regressed before P8-B0")


def main() -> int:
    asset_set = validate_asset_set(_json(ASSET_SET))
    request_set = _json(REQUEST_SET)
    raw_members = request_set.get("members")
    if type(raw_members) is not list:
        raise SystemExit("request manifest members malformed")

    payloads: dict[str, object] = {}
    for raw in cast(list[object], raw_members):
        if type(raw) is not dict:
            raise SystemExit("request manifest member malformed")
        member = cast(dict[str, object], raw)
        ref = member.get("request_ref")
        if type(ref) is not str:
            raise SystemExit("request_ref malformed")
        payloads[ref] = _json(REQUEST_ROOT / ref)

    validate_asset_set_request_payloads(request_set, asset_set, payloads)
    set_digest = asset_set_sha256(asset_set)
    if set_digest != EXPECTED_ASSET_SET_SHA256:
        raise SystemExit("reference AssetSet digest drifted")
    request_digest = asset_set_request_sha256(request_set, asset_set, payloads)
    if request_digest != EXPECTED_REQUEST_SHA256:
        raise SystemExit("reference AssetSetRequest digest drifted")

    built = build_asset_set_schedule(request_set, asset_set, payloads)
    retained = _json(SCHEDULE)
    if built != retained:
        raise SystemExit("retained schedule is not the exact deterministic projection")
    validate_asset_set_schedule(retained, request_set, asset_set, payloads)

    red = cast(dict[str, object], payloads["requests/potion-red.json"])
    blue = cast(dict[str, object], payloads["requests/potion-blue.json"])
    if red.get("art_intent") != blue.get("art_intent"):
        raise SystemExit("potion variants should share structural ArtIntent in this fixture")
    shared_profiles = asset_set["shared_profiles"]
    if asset_request_sha256(red, shared_profiles=shared_profiles) == asset_request_sha256(
        blue,
        shared_profiles=shared_profiles,
    ):
        raise SystemExit("semantic instruction must participate in member request identity")

    _validate_lane(_json(CORE_LANE))
    members = cast(list[dict[str, object]], retained["members"])
    print(
        json.dumps(
            {
                "schema": "tracepixel.p8-b0-checkpoint.v1",
                "asset_set_sha256": set_digest,
                "request_sha256": request_digest,
                "member_count": len(members),
                "member_order": [member["member_id"] for member in members],
                "dispatch_policy": retained["dispatch_policy"],
                "max_concurrency": retained["max_concurrency"],
                "request_payloads_valid": True,
                "provider_invoked": False,
                "schedule_executed": False,
                "raster_authority_created": False,
                "next": "P8-B1",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
