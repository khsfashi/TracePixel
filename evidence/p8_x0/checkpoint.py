from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tracepixel.model.asset_set_validation import validate_asset_set

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "evidence" / "p8_x0" / "reference-asset-set.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _validate_lane(lane: dict[str, object]) -> None:
    sequence = lane.get("sequence")
    current = lane.get("current")
    if type(sequence) is not list or type(current) is not str:
        raise SystemExit("core lane sequence/current malformed")
    phases = cast(list[object], sequence)
    if not all(type(item) is str for item in phases):
        raise SystemExit("core lane sequence must contain strings")
    names = cast(list[str], phases)
    if "P8" not in names or current not in names or names.index(current) < names.index("P8"):
        raise SystemExit("P8-X0 checkpoint requires the core lane to remain at or beyond P8")
    if current == "P8":
        children = lane.get("child_sequences")
        if type(children) is not dict:
            raise SystemExit("core lane child_sequences malformed")
        p8 = cast(dict[str, object], children).get("P8")
        child = lane.get("current_child")
        if type(p8) is not list or child not in cast(list[object], p8):
            raise SystemExit("active P8 child is not declared")
        child_names = cast(list[str], p8)
        if child_names.index(cast(str, child)) < child_names.index("P8-X0"):
            raise SystemExit("core lane regressed before P8-X0")
        if lane.get("active_issue") != 92:
            raise SystemExit("active P8 work must remain on issue #92")


def main() -> int:
    fixture = _json(FIXTURE)
    lane = _json(CORE_LANE)
    validated = validate_asset_set(fixture)
    _validate_lane(lane)

    members = cast(list[dict[str, object]], validated["members"])
    execution = cast(dict[str, object], validated["execution"])
    profiles = cast(list[dict[str, object]], validated["shared_profiles"])
    if [member["member_id"] for member in members] != ["potion-red", "potion-blue", "leaf-green"]:
        raise SystemExit("declared member order drifted")
    if execution["member_authority"] != "single-asset-pipeline" or execution["failure_policy"] != "isolate-member":
        raise SystemExit("batch authority/failure isolation drifted")
    if not all(type(profile.get("sha256")) is str and len(cast(str, profile["sha256"])) == 64 for profile in profiles):
        raise SystemExit("shared profiles must remain digest-pinned")

    print(
        json.dumps(
            {
                "schema": "tracepixel.p8-x0-checkpoint.v1",
                "asset_set_schema": validated["schema"],
                "member_count": len(members),
                "max_concurrency": execution["max_concurrency"],
                "member_authority": execution["member_authority"],
                "failure_policy": execution["failure_policy"],
                "shared_profile_kinds": [profile["kind"] for profile in profiles],
                "provider_invoked": False,
                "raster_authority_created": False,
                "next": "P8-R0",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
