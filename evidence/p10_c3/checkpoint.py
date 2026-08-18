from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tracepixel.model.asset_set_schedule_validation import asset_request_sha256
from tracepixel.model.creature_pose_validation import validate_creature_pose, validate_creature_pose_reference
from tracepixel.model.research_profile_validation import (
    validate_morphology_profile_reference,
    validate_simple_creature_morphology_profile,
)
from tracepixel.model.simple_creature_request import (
    DETERMINISTIC_EVIDENCE_FACTS_V1,
    PERCEPTUAL_EVIDENCE_FACTS_V1,
)
from tracepixel.model.simple_creature_request_validation import (
    simple_creature_evidence_policy_sha256,
    validate_simple_creature_request,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "evidence" / "p10_c1" / "simple-creature-profile.v1.json"
PROFILE_REF = ROOT / "evidence" / "p10_c1" / "simple-creature-profile-ref.v1.json"
POSE = ROOT / "evidence" / "p10_c2" / "creature-pose.v1.json"
POSE_REF = ROOT / "evidence" / "p10_c2" / "creature-pose-ref.v1.json"
POLICY = ROOT / "evidence" / "p10_c3" / "simple-creature-evidence-policy.v1.json"
POLICY_REF = ROOT / "evidence" / "p10_c3" / "simple-creature-evidence-policy-ref.v1.json"
ASSET_REQUEST = ROOT / "evidence" / "p10_c3" / "asset-request.v1.json"
CREATURE_REQUEST = ROOT / "evidence" / "p10_c3" / "simple-creature-request.v1.json"
C0_CONTRACT = ROOT / "evidence" / "p10_c0" / "promotion-contract.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"P10-C3 checkpoint failed: {message}")


def main() -> int:
    profile = _json(PROFILE)
    profile_ref = _json(PROFILE_REF)
    pose = _json(POSE)
    pose_ref = _json(POSE_REF)
    policy = _json(POLICY)
    policy_ref = _json(POLICY_REF)
    asset_request = _json(ASSET_REQUEST)
    creature_request = _json(CREATURE_REQUEST)
    contract = _json(C0_CONTRACT)
    lane = _json(CORE_LANE)

    validated_profile = validate_simple_creature_morphology_profile(profile)
    validate_morphology_profile_reference(profile_ref, validated_profile)
    validated_pose = validate_creature_pose(pose, validated_profile)
    validate_creature_pose_reference(pose_ref, validated_pose, validated_profile)
    validate_simple_creature_request(
        creature_request,
        asset_request=asset_request,
        morphology_profile=validated_profile,
        creature_pose=validated_pose,
        evidence_policy=policy,
    )

    _expect(creature_request.get("morphology_ref") == profile_ref, "request morphology ref is not the retained C1 ref")
    _expect(creature_request.get("pose_ref") == pose_ref, "request pose ref is not the retained C2 ref")
    _expect(creature_request.get("request_sha256") == asset_request_sha256(asset_request), "single-asset request digest drifted")
    _expect(policy_ref.get("sha256") == simple_creature_evidence_policy_sha256(policy), "evidence policy digest drifted")
    _expect(creature_request.get("evidence_policy_ref") == policy_ref, "request is not bound to the retained evidence policy")

    art_intent = cast(dict[str, object], asset_request.get("art_intent"))
    _expect(art_intent.get("asset_class") == "simple-creature", "bound AssetRequest is not simple-creature")

    authority = cast(dict[str, object], contract.get("evidence_authority"))
    _expect(tuple(cast(list[object], policy.get("deterministic_facts"))) == DETERMINISTIC_EVIDENCE_FACTS_V1, "deterministic evidence list drifted")
    _expect(tuple(cast(list[object], policy.get("perceptual_facts"))) == PERCEPTUAL_EVIDENCE_FACTS_V1, "perceptual evidence list drifted")
    _expect(policy.get("deterministic_facts") == authority.get("deterministic_facts"), "policy diverged from frozen C0 deterministic authority")
    _expect(policy.get("perceptual_facts") == authority.get("perceptual_facts"), "policy diverged from frozen C0 perceptual authority")
    _expect(policy.get("vlm_is_deterministic_correctness") is False, "VLM was promoted to deterministic correctness")
    _expect(policy.get("final_aesthetic_acceptance") == "human", "final aesthetic acceptance is no longer human")

    scope = cast(dict[str, object], contract.get("scope"))
    _expect(scope.get("creature_raster_generation_allowed") is False, "C3 must not enable creature raster generation")
    _expect(scope.get("creature_provider_execution_allowed") is False, "C3 must not enable creature provider execution")
    _expect(scope.get("new_raster_authority_allowed") is False, "C3 must not add raster authority")

    _expect(lane.get("current") == "P10", "core lane is not P10")
    _expect(lane.get("current_child") == "P10-C3", "core lane is not P10-C3")
    _expect(lane.get("active_issue") == 109, "P10-C3 is not bound to issue #109")

    print(json.dumps({
        "schema": "tracepixel.p10-c3-checkpoint.v1",
        "status": "pass",
        "source_issue": 109,
        "current_child": "P10-C3",
        "next_child": "P10-C4",
        "asset_request_sha256": creature_request["request_sha256"],
        "morphology_sha256": profile_ref["sha256"],
        "pose_sha256": pose_ref["sha256"],
        "evidence_policy_sha256": policy_ref["sha256"],
        "provider_calls": 0,
        "raster_generation": 0,
        "perceptual_scoring": 0,
        "new_raster_authority": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
