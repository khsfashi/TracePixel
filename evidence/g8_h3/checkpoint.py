from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from evidence.g8_h2.forward_checkpoint import main as g8_h2_forward_main
from tracepixel.model.asset_set_schedule_validation import asset_request_sha256
from tracepixel.model.humanoid_pose_validation import validate_humanoid_pose, validate_humanoid_pose_reference
from tracepixel.model.humanoid_profile_validation import validate_humanoid_profile, validate_humanoid_profile_reference
from tracepixel.model.static_humanoid_request import (
    DETERMINISTIC_EVIDENCE_FACTS_V1,
    PERCEPTUAL_EVIDENCE_FACTS_V1,
)
from tracepixel.model.static_humanoid_request_validation import (
    static_humanoid_evidence_policy_sha256,
    validate_static_humanoid_request,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "evidence" / "g8_h1" / "humanoid-profile.v1.json"
PROFILE_REF = ROOT / "evidence" / "g8_h1" / "humanoid-profile-ref.v1.json"
POSE = ROOT / "evidence" / "g8_h2" / "humanoid-pose.v1.json"
POSE_REF = ROOT / "evidence" / "g8_h2" / "humanoid-pose-ref.v1.json"
POLICY = ROOT / "evidence" / "g8_h3" / "static-humanoid-evidence-policy.v1.json"
POLICY_REF = ROOT / "evidence" / "g8_h3" / "static-humanoid-evidence-policy-ref.v1.json"
ASSET_REQUEST = ROOT / "evidence" / "g8_h3" / "asset-request.v1.json"
HUMANOID_REQUEST = ROOT / "evidence" / "g8_h3" / "static-humanoid-request.v1.json"
H0_CONTRACT = ROOT / "evidence" / "g8_h0" / "promotion-contract.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"G8-H3 checkpoint failed: {message}")


def main() -> int:
    _expect(g8_h2_forward_main() == 0, "G8-H2 historical checkpoint failed")

    profile = _json(PROFILE)
    profile_ref = _json(PROFILE_REF)
    pose = _json(POSE)
    pose_ref = _json(POSE_REF)
    policy = _json(POLICY)
    policy_ref = _json(POLICY_REF)
    asset_request = _json(ASSET_REQUEST)
    humanoid_request = _json(HUMANOID_REQUEST)
    contract = _json(H0_CONTRACT)
    lane = _json(CORE_LANE)

    validated_profile = validate_humanoid_profile(profile)
    validate_humanoid_profile_reference(profile_ref, validated_profile)
    validated_pose = validate_humanoid_pose(pose, validated_profile)
    validate_humanoid_pose_reference(pose_ref, validated_pose, validated_profile)
    validate_static_humanoid_request(
        humanoid_request,
        asset_request=asset_request,
        humanoid_profile=validated_profile,
        humanoid_pose=validated_pose,
        evidence_policy=policy,
    )

    _expect(humanoid_request.get("profile_ref") == profile_ref, "request profile ref is not the retained H1 ref")
    _expect(humanoid_request.get("pose_ref") == pose_ref, "request pose ref is not the retained H2 ref")
    _expect(humanoid_request.get("request_sha256") == asset_request_sha256(asset_request), "single-asset request digest drifted")
    _expect(policy_ref.get("sha256") == static_humanoid_evidence_policy_sha256(policy), "evidence policy digest drifted")
    _expect(humanoid_request.get("evidence_policy_ref") == policy_ref, "request is not bound to the retained evidence policy")

    art_intent = cast(dict[str, object], asset_request.get("art_intent"))
    _expect(art_intent.get("asset_class") == "static-humanoid-character", "bound AssetRequest is not static-humanoid-character")
    profile_refs = cast(list[object], asset_request.get("profile_refs"))
    _expect(len(profile_refs) == 1, "bound AssetRequest must carry exactly one retained humanoid profile")
    bound_profile = cast(dict[str, object], profile_refs[0])
    _expect(bound_profile.get("kind") == "morphology", "humanoid profile must reuse the existing morphology profile seam")
    _expect(
        {key: bound_profile.get(key) for key in ("profile_id", "profile_schema", "sha256")} == profile_ref,
        "AssetRequest profile binding is not the exact retained H1 ref",
    )

    authority = cast(dict[str, object], contract.get("evidence_authority"))
    _expect(tuple(cast(list[object], policy.get("deterministic_facts"))) == DETERMINISTIC_EVIDENCE_FACTS_V1, "deterministic evidence list drifted")
    _expect(tuple(cast(list[object], policy.get("perceptual_facts"))) == PERCEPTUAL_EVIDENCE_FACTS_V1, "perceptual evidence list drifted")
    _expect(policy.get("deterministic_facts") == authority.get("deterministic_facts"), "policy diverged from frozen H0 deterministic authority")
    _expect(policy.get("perceptual_facts") == authority.get("perceptual_facts"), "policy diverged from frozen H0 perceptual authority")
    _expect(policy.get("vlm_is_deterministic_correctness") is False, "VLM was promoted to deterministic correctness")
    _expect(policy.get("final_aesthetic_acceptance") == "human", "final aesthetic acceptance is no longer human")

    scope = cast(dict[str, object], contract.get("scope"))
    _expect(scope.get("humanoid_raster_generation_allowed") is False, "H3 must not enable humanoid raster generation")
    _expect(scope.get("humanoid_provider_execution_allowed") is False, "H3 must not enable humanoid provider execution")
    _expect(scope.get("new_raster_authority_allowed") is False, "H3 must not add raster authority")
    _expect(scope.get("equipment_second_raster_authority_allowed") is False, "H3 must not add equipment raster authority")
    _expect(scope.get("animation_implementation_allowed") is False, "H3 must not pull animation forward")

    authority_contract = cast(dict[str, object], contract.get("authority"))
    _expect(authority_contract.get("single_asset_pixelprogram_canvas_reused") is True, "single-asset PixelProgram/Canvas authority is no longer reused")
    _expect(authority_contract.get("second_humanoid_drawing_engine_allowed") is False, "second humanoid drawing engine was authorized")
    _expect(authority_contract.get("skeletal_or_physics_authority_allowed") is False, "skeletal/physics authority was authorized")
    _expect(authority_contract.get("hidden_humanoid_scheduler_provider_work_allowed") is False, "hidden humanoid provider scheduling was authorized")

    _expect(lane.get("current") == "G8", "core lane is not G8")
    _expect(lane.get("current_child") == "G8-H3", "core lane is not G8-H3")
    _expect(lane.get("active_issue") == 119, "G8-H3 is not bound to issue #119")

    print(json.dumps({
        "schema": "tracepixel.g8-h3-checkpoint.v1",
        "status": "pass",
        "source_issue": 119,
        "current_child": "G8-H3",
        "next_child": "G8-H4",
        "asset_request_sha256": humanoid_request["request_sha256"],
        "profile_sha256": profile_ref["sha256"],
        "pose_sha256": pose_ref["sha256"],
        "evidence_policy_sha256": policy_ref["sha256"],
        "provider_calls": 0,
        "humanoid_raster_generation": 0,
        "perceptual_scoring": 0,
        "physics_or_ik_added": False,
        "raster_authority_added": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
