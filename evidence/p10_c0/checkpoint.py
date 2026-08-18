from __future__ import annotations

import json
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "evidence" / "p10_c0" / "promotion-contract.v1.json"
P8_POSTMORTEM = ROOT / "evidence" / "p8_b6" / "postmortem.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"P10-C0 checkpoint failed: {message}")


def main() -> int:
    contract = _json(CONTRACT)
    postmortem = _json(P8_POSTMORTEM)
    lane = _json(CORE_LANE)

    _expect(contract.get("schema") == "tracepixel.p10-c0-promotion-contract.v1", "contract schema drifted")
    _expect(contract.get("source_issue") == 109, "promotion must remain bound to issue #109")
    _expect(contract.get("owner_gate") == "G7", "simple-creature promotion must remain bound to G7")
    _expect(contract.get("owner_decision_date") == "2026-08-17", "recorded owner decision date drifted")
    _expect(contract.get("status") == "contract-frozen", "promotion contract is not frozen")

    prerequisites = cast(dict[str, object], contract.get("prerequisites"))
    _expect(prerequisites.get("p8_b6_postmortem") == "frozen-complete", "P8-B6 prerequisite is not frozen-complete")
    _expect(prerequisites.get("g7_simple_creature_direction") == "owner-approved", "G7 owner direction is not recorded as approved")
    _expect(postmortem.get("schema") == "tracepixel.p8-b6-postmortem.v1", "P8-B6 postmortem schema drifted")
    _expect(postmortem.get("status") == "frozen-complete", "P8-B6 is not frozen complete")
    post_p8 = cast(dict[str, object], postmortem.get("post_p8"))
    _expect(post_p8.get("g7_simple_creature_direction") == "owner-approved", "P8-B6 handoff no longer approves G7 direction")
    _expect(post_p8.get("g7_issue") == 109, "P8-B6 G7 issue binding drifted")

    _expect(lane.get("current") == "P10", "core lane is not P10")
    _expect(lane.get("current_child") == "P10-C0", "core lane is not P10-C0")
    _expect(lane.get("active_issue") == 109, "core lane is not bound to issue #109")
    sequence = cast(list[object], lane.get("sequence"))
    _expect("P8" in sequence and "P10" in sequence and "P9" in sequence, "P8/P10/P9 sequence entries are missing")
    _expect(sequence.index("P8") < sequence.index("P10") < sequence.index("P9"), "P10 must follow P8 and precede gated P9")
    children = cast(dict[str, object], lane.get("child_sequences"))
    p10 = cast(list[object], children.get("P10"))
    expected_children = ["P10-C0", "P10-C1", "P10-C2", "P10-C3", "P10-C4", "P10-C5"]
    _expect(p10 == expected_children, "P10 child sequence drifted")

    contract_lane = cast(dict[str, object], contract.get("lane"))
    _expect(contract_lane.get("phase") == "P10", "contract phase drifted")
    _expect(contract_lane.get("current_child") == "P10-C0", "contract child drifted")
    _expect(contract_lane.get("children") == expected_children, "contract child sequence does not match core lane")
    _expect(contract_lane.get("next_child") == "P10-C1", "P10-C0 must hand off only to P10-C1")

    scope = cast(dict[str, object], contract.get("scope"))
    _expect(scope.get("asset_class") == "simple-creature", "promotion scope is not simple-creature")
    for key in (
        "creature_raster_generation_allowed",
        "creature_provider_execution_allowed",
        "humanoid_implementation_allowed",
        "animation_implementation_allowed",
        "trace2d_adapter_allowed",
        "new_raster_authority_allowed",
    ):
        _expect(scope.get(key) is False, f"P10-C0 prohibition drifted: {key}")
    _expect(scope.get("physical_simulation_required") is False, "P10 must not require physical simulation")

    morphology = cast(dict[str, object], contract.get("morphology_profile"))
    _expect(morphology.get("planned_schema") == "tracepixel.morphology-profile.v1", "morphology schema target drifted")
    _expect(morphology.get("versioned") is True and morphology.get("digest_pinned") is True, "morphology profile must be immutable/digest-pinned")
    _expect(morphology.get("authority") == "research-evidence-and-authoring-context-only", "morphology authority widened")
    _expect(morphology.get("constraint_modes") == ["required-range", "hint", "stylization-tolerance"], "morphology constraint modes drifted")
    _expect(morphology.get("is_raster_authority") is False, "morphology profile cannot become raster authority")
    required_categories = cast(list[object], morphology.get("required_categories"))
    _expect(len(required_categories) == 10 and len(set(cast(list[str], required_categories))) == 10, "morphology required category set malformed")

    pose = cast(dict[str, object], contract.get("pose_constraint"))
    _expect(pose.get("planned_schema") == "tracepixel.creature-pose.v1", "pose schema target drifted")
    _expect(pose.get("binds_morphology_digest") is True, "pose intent must bind the morphology profile digest")
    _expect(pose.get("constraint_modes") == morphology.get("constraint_modes"), "pose and morphology constraint modes diverged")
    _expect(pose.get("is_physics_engine") is False and pose.get("is_skeletal_raster_authority") is False, "pose contract widened into a second engine")

    evidence = cast(dict[str, object], contract.get("evidence_authority"))
    deterministic = cast(list[object], evidence.get("deterministic_facts"))
    perceptual = cast(list[object], evidence.get("perceptual_facts"))
    _expect(len(deterministic) >= 8, "deterministic evidence responsibilities are incomplete")
    _expect(len(perceptual) >= 5, "perceptual evidence responsibilities are incomplete")
    _expect(evidence.get("vlm_is_deterministic_correctness") is False, "VLM cannot become deterministic truth")
    _expect(evidence.get("final_aesthetic_acceptance") == "human", "final aesthetic acceptance must remain human")

    complexity = cast(dict[str, object], contract.get("complexity"))
    _expect(complexity.get("reuse_existing_single_asset_accounting") is True, "creature work must reuse single-asset cost accounting")
    metrics = cast(list[object], complexity.get("required_metrics"))
    for required in ("provider-calls", "input-tokens", "output-tokens", "pixel-edits", "changed-pixels", "wall-time", "failure-category"):
        _expect(required in metrics, f"complexity metric missing: {required}")
    _expect(complexity.get("research_profile_cost_separately_attributable") is True, "research/profile cost must remain separately attributable")
    _expect(complexity.get("synthetic_quality_cost_winner_allowed") is False, "synthetic quality/cost winner must remain forbidden")
    _expect(complexity.get("b1_single_member_staged_cost_warning_resolved") is False, "P10-C0 cannot claim the B1 staged-cost warning is solved")

    authority = cast(dict[str, object], contract.get("authority"))
    _expect(authority.get("single_asset_pixelprogram_canvas_reused") is True, "existing single-asset raster authority must be reused")
    _expect(authority.get("morphology_or_pose_becomes_pixel_authority") is False, "morphology/pose cannot become pixel authority")
    _expect(authority.get("second_creature_drawing_engine_allowed") is False, "second creature drawing engine is forbidden")
    _expect(authority.get("hidden_creature_scheduler_provider_work_allowed") is False, "hidden creature scheduler/provider work is forbidden")

    print(json.dumps({
        "schema": "tracepixel.p10-c0-checkpoint.v1",
        "status": "pass",
        "source_issue": 109,
        "current_child": "P10-C0",
        "next_child": "P10-C1",
        "provider_calls": 0,
        "raster_generation": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
