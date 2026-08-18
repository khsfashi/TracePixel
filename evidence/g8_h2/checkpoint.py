from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from evidence.g8_h1.forward_checkpoint import main as g8_h1_forward_main
from tracepixel.model.humanoid_pose_validation import (
    humanoid_pose_sha256,
    validate_humanoid_pose,
    validate_humanoid_pose_reference,
)
from tracepixel.model.humanoid_profile_validation import (
    validate_humanoid_profile,
    validate_humanoid_profile_reference,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "evidence" / "g8_h1" / "humanoid-profile.v1.json"
PROFILE_REF = ROOT / "evidence" / "g8_h1" / "humanoid-profile-ref.v1.json"
POSE = ROOT / "evidence" / "g8_h2" / "humanoid-pose.v1.json"
POSE_REF = ROOT / "evidence" / "g8_h2" / "humanoid-pose-ref.v1.json"
H0_CONTRACT = ROOT / "evidence" / "g8_h0" / "promotion-contract.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"

REQUIRED_RELATIONS = {"articulation", "support-contact", "balance-contact", "silhouette-facing"}
REQUIRED_CAPABILITIES = {
    "named-static-pose-and-orientation-intent",
    "body-landmark-or-joint-relations",
    "bounded-articulation-ranges",
    "support-and-contact-landmarks",
    "coarse-balance-and-contact-intent",
    "silhouette-facing-expectations",
    "equipment-anchor-identity-and-reference-integrity",
    "equipment-anchor-occupancy-and-side-intent",
    "attachment-overlap-or-occlusion-intent",
}


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"G8-H2 checkpoint failed: {message}")


def main() -> int:
    _expect(g8_h1_forward_main() == 0, "G8-H1 historical checkpoint failed")

    profile = _json(PROFILE)
    profile_ref = _json(PROFILE_REF)
    pose = _json(POSE)
    pose_ref = _json(POSE_REF)
    contract = _json(H0_CONTRACT)
    lane = _json(CORE_LANE)

    validated_profile = validate_humanoid_profile(profile)
    validate_humanoid_profile_reference(profile_ref, validated_profile)
    validated_pose = validate_humanoid_pose(pose, validated_profile)
    validate_humanoid_pose_reference(pose_ref, validated_pose, validated_profile)

    _expect(pose.get("schema") == "tracepixel.humanoid-pose.v1", "pose schema drifted")
    _expect(pose.get("profile_ref") == profile_ref, "pose is not bound to the exact retained H1 profile reference")
    _expect(pose_ref.get("sha256") == humanoid_pose_sha256(validated_pose, validated_profile), "retained pose digest drifted")

    orientation = cast(dict[str, object], pose.get("orientation_intent"))
    _expect(type(orientation.get("facing")) is str, "named pose has no facing intent")
    _expect(type(orientation.get("description")) is str, "named pose has no orientation description")

    relations = cast(list[object], pose.get("relations"))
    relation_kinds = {cast(dict[str, object], item).get("kind") for item in relations}
    _expect(REQUIRED_RELATIONS <= relation_kinds, "required articulation/support/balance/silhouette relations are incomplete")
    _expect(any(cast(dict[str, object], item).get("kind") == "landmark-relation" for item in relations), "body landmark relation is missing")
    articulation = next(cast(dict[str, object], item) for item in relations if cast(dict[str, object], item).get("kind") == "articulation")
    articulation_range = cast(dict[str, object], articulation.get("value_range"))
    _expect(articulation.get("mode") == "required-range", "retained articulation is not a required range")
    _expect(articulation_range.get("unit") == "degrees", "retained articulation is not degree-bounded")

    attachments = cast(list[object], pose.get("equipment_attachments"))
    _expect(len(attachments) >= 1, "equipment anchor occupancy declarations are missing")
    _expect(any(cast(dict[str, object], item).get("occupancy_intent") == "occupied" for item in attachments), "occupied equipment anchor evidence is missing")
    _expect(any(cast(dict[str, object], item).get("overlap_occlusion_intent") != "none" for item in attachments), "attachment overlap/occlusion intent is missing")

    pose_contract = cast(dict[str, object], contract.get("pose_equipment_constraint"))
    _expect(pose_contract.get("planned_schema") == pose.get("schema"), "H2 pose schema diverged from frozen H0 contract")
    _expect(pose_contract.get("binds_profile_digest") is True, "H0 profile digest binding requirement drifted")
    capabilities = pose_contract.get("required_capabilities")
    _expect(type(capabilities) is list and set(cast(list[object], capabilities)) == REQUIRED_CAPABILITIES, "H0 required pose/equipment capabilities drifted")
    _expect(pose_contract.get("equipment_anchor_is_pixel_authority") is False, "equipment anchors widened into pixel authority")
    _expect(pose_contract.get("is_physics_engine") is False, "pose widened into a physics engine")
    _expect(pose_contract.get("is_inverse_kinematics_solver") is False, "pose widened into an IK solver")
    _expect(pose_contract.get("is_skeletal_raster_authority") is False, "pose widened into skeletal raster authority")

    scope = cast(dict[str, object], contract.get("scope"))
    _expect(scope.get("humanoid_provider_execution_allowed") is False, "H2 cannot authorize provider execution")
    _expect(scope.get("humanoid_raster_generation_allowed") is False, "H2 cannot authorize humanoid raster generation")
    _expect(scope.get("new_raster_authority_allowed") is False, "H2 cannot add raster authority")
    _expect(scope.get("equipment_second_raster_authority_allowed") is False, "H2 cannot add equipment raster authority")

    _expect(lane.get("current") == "G8", "core lane is not G8")
    _expect(lane.get("current_child") == "G8-H2", "core lane is not G8-H2")
    _expect(lane.get("active_issue") == 119, "G8-H2 is not bound to issue #119")
    children = cast(dict[str, object], lane.get("child_sequences"))
    g8 = cast(list[object], children.get("G8"))
    _expect(g8 == ["G8-H0", "G8-H1", "G8-H2", "G8-H3", "G8-H4", "G8-H5"], "G8 child sequence drifted")

    print(json.dumps({
        "schema": "tracepixel.g8-h2-checkpoint.v1",
        "status": "pass",
        "source_issue": 119,
        "current_child": "G8-H2",
        "next_child": "G8-H3",
        "pose_schema": pose["schema"],
        "pose_sha256": pose_ref["sha256"],
        "profile_sha256": profile_ref["sha256"],
        "relation_count": len(relations),
        "equipment_attachment_count": len(attachments),
        "provider_calls": 0,
        "humanoid_raster_generation": 0,
        "physics_or_ik_added": False,
        "raster_authority_added": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
