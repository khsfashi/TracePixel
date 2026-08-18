from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tracepixel.model.creature_pose_validation import (
    creature_pose_sha256,
    validate_creature_pose,
    validate_creature_pose_reference,
)
from tracepixel.model.research_profile_validation import (
    validate_morphology_profile_reference,
    validate_simple_creature_morphology_profile,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "evidence" / "p10_c1" / "simple-creature-profile.v1.json"
PROFILE_REF = ROOT / "evidence" / "p10_c1" / "simple-creature-profile-ref.v1.json"
POSE = ROOT / "evidence" / "p10_c2" / "creature-pose.v1.json"
POSE_REF = ROOT / "evidence" / "p10_c2" / "creature-pose-ref.v1.json"
C0_CONTRACT = ROOT / "evidence" / "p10_c0" / "promotion-contract.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"

REQUIRED_RELATIONS = {"articulation", "support-contact", "silhouette-facing"}


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"P10-C2 checkpoint failed: {message}")


def main() -> int:
    profile = _json(PROFILE)
    profile_ref = _json(PROFILE_REF)
    pose = _json(POSE)
    pose_ref = _json(POSE_REF)
    contract = _json(C0_CONTRACT)
    lane = _json(CORE_LANE)

    validated_profile = validate_simple_creature_morphology_profile(profile)
    validate_morphology_profile_reference(profile_ref, validated_profile)
    validated_pose = validate_creature_pose(pose, validated_profile)
    validate_creature_pose_reference(pose_ref, validated_pose, validated_profile)

    _expect(pose.get("schema") == "tracepixel.creature-pose.v1", "pose schema drifted")
    _expect(pose.get("morphology_ref") == profile_ref, "pose is not bound to the exact retained C1 morphology reference")
    _expect(pose_ref.get("sha256") == creature_pose_sha256(validated_pose, validated_profile), "retained pose digest drifted")

    orientation = cast(dict[str, object], pose.get("orientation_intent"))
    _expect(type(orientation.get("facing")) is str, "named pose has no facing intent")
    _expect(type(orientation.get("description")) is str, "named pose has no orientation description")

    relations = cast(list[object], pose.get("relations"))
    relation_kinds = {cast(dict[str, object], item).get("kind") for item in relations}
    _expect(REQUIRED_RELATIONS <= relation_kinds, "required articulation/support/silhouette pose relations are incomplete")
    articulation = next(cast(dict[str, object], item) for item in relations if cast(dict[str, object], item).get("kind") == "articulation")
    articulation_range = cast(dict[str, object], articulation.get("value_range"))
    _expect(articulation.get("mode") == "required-range", "retained articulation is not a required range")
    _expect(articulation_range.get("unit") == "degrees", "retained articulation is not degree-bounded")

    pose_contract = cast(dict[str, object], contract.get("pose_constraint"))
    _expect(pose_contract.get("planned_schema") == pose.get("schema"), "C2 pose schema diverged from frozen C0 contract")
    _expect(pose_contract.get("binds_morphology_digest") is True, "C0 morphology digest binding requirement drifted")
    _expect(pose_contract.get("is_physics_engine") is False, "pose widened into a physics engine")
    _expect(pose_contract.get("is_skeletal_raster_authority") is False, "pose widened into skeletal raster authority")

    scope = cast(dict[str, object], contract.get("scope"))
    _expect(scope.get("creature_raster_generation_allowed") is False, "C2 must not enable creature raster generation")
    _expect(scope.get("creature_provider_execution_allowed") is False, "C2 must not enable creature provider execution")
    _expect(scope.get("new_raster_authority_allowed") is False, "C2 must not add raster authority")

    _expect(lane.get("current") == "P10", "core lane is not P10")
    _expect(lane.get("current_child") == "P10-C2", "core lane is not P10-C2")
    _expect(lane.get("active_issue") == 109, "P10-C2 is not bound to issue #109")

    print(json.dumps({
        "schema": "tracepixel.p10-c2-checkpoint.v1",
        "status": "pass",
        "source_issue": 109,
        "current_child": "P10-C2",
        "next_child": "P10-C3",
        "pose_schema": pose["schema"],
        "pose_sha256": pose_ref["sha256"],
        "morphology_sha256": profile_ref["sha256"],
        "provider_calls": 0,
        "raster_generation": 0,
        "physics_or_ik_added": False,
        "raster_authority_added": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
