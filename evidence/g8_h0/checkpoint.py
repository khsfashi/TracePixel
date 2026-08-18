from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from evidence.p10_c5.forward_checkpoint import main as p10_c5_forward_main

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "evidence" / "g8_h0" / "promotion-contract.v1.json"
P10_POSTMORTEM = ROOT / "evidence" / "p10_c5" / "postmortem.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"G8-H0 checkpoint failed: {message}")


def main() -> int:
    _expect(p10_c5_forward_main() == 0, "P10-C5 historical checkpoint failed")

    contract = _json(CONTRACT)
    postmortem = _json(P10_POSTMORTEM)
    lane = _json(CORE_LANE)

    _expect(contract.get("schema") == "tracepixel.g8-h0-promotion-contract.v1", "contract schema drifted")
    _expect(contract.get("source_issue") == 119, "promotion must remain bound to issue #119")
    _expect(contract.get("owner_gate") == "G8", "humanoid promotion must remain bound to G8")
    _expect(contract.get("owner_decision_date") == "2026-08-17", "recorded owner decision date drifted")
    _expect(contract.get("status") == "contract-frozen", "promotion contract is not frozen")

    prerequisites = cast(dict[str, object], contract.get("prerequisites"))
    _expect(prerequisites.get("p10_c5_postmortem") == "frozen-complete", "P10-C5 prerequisite is not frozen-complete")
    _expect(prerequisites.get("g8_humanoid_direction") == "owner-approved", "G8 owner direction is not recorded as approved")
    _expect(postmortem.get("schema") == "tracepixel.p10-c5-postmortem.v1", "P10-C5 postmortem schema drifted")
    _expect(postmortem.get("status") == "frozen-complete", "P10-C5 is not frozen complete")
    quality = cast(dict[str, object], postmortem.get("quality"))
    _expect(quality.get("owner_verdict") == "accepted", "simple-creature prerequisite lacks owner acceptance")
    post_p10 = cast(dict[str, object], postmortem.get("post_p10"))
    _expect(post_p10.get("g8_humanoid_direction") == "owner-approved-long-term-destination-contract-lane-next", "P10 handoff no longer authorizes the G8 contract lane")
    _expect(post_p10.get("g9_animation_direction") == "blocked-until-humanoid-promotion-evidence", "G9 sequencing prerequisite drifted")

    _expect(lane.get("current") == "G8", "core lane is not G8")
    _expect(lane.get("current_child") == "G8-H0", "core lane is not G8-H0")
    _expect(lane.get("active_issue") == 119, "core lane is not bound to issue #119")
    sequence = cast(list[object], lane.get("sequence"))
    _expect("P10" in sequence and "G8" in sequence and "P9" in sequence, "P10/G8/P9 sequence entries are missing")
    _expect(sequence.index("P10") < sequence.index("G8") < sequence.index("P9"), "G8 must follow P10 and precede gated P9")
    children = cast(dict[str, object], lane.get("child_sequences"))
    g8 = cast(list[object], children.get("G8"))
    expected_children = ["G8-H0", "G8-H1", "G8-H2", "G8-H3", "G8-H4", "G8-H5"]
    _expect(g8 == expected_children, "G8 child sequence drifted")

    contract_lane = cast(dict[str, object], contract.get("lane"))
    _expect(contract_lane.get("phase") == "G8", "contract phase drifted")
    _expect(contract_lane.get("current_child") == "G8-H0", "contract child drifted")
    _expect(contract_lane.get("children") == expected_children, "contract child sequence does not match core lane")
    _expect(contract_lane.get("next_child") == "G8-H1", "G8-H0 must hand off only to G8-H1")
    _expect(contract_lane.get("humanoid_provider_or_raster_earliest_child") == "G8-H4", "humanoid authoring must remain blocked until H4")

    scope = cast(dict[str, object], contract.get("scope"))
    _expect(scope.get("asset_class") == "static-humanoid-character", "promotion scope is not static humanoid")
    for key in (
        "humanoid_raster_generation_allowed",
        "humanoid_provider_execution_allowed",
        "animation_implementation_allowed",
        "trace2d_adapter_allowed",
        "new_raster_authority_allowed",
        "skeletal_simulation_required",
        "inverse_kinematics_required",
        "equipment_second_raster_authority_allowed",
    ):
        _expect(scope.get(key) is False, f"G8-H0 prohibition drifted: {key}")

    profile = cast(dict[str, object], contract.get("anatomy_identity_profile"))
    _expect(profile.get("planned_schema") == "tracepixel.humanoid-profile.v1", "humanoid profile schema target drifted")
    _expect(profile.get("versioned") is True and profile.get("digest_pinned") is True, "humanoid profile must be immutable/digest-pinned")
    _expect(profile.get("reuse_existing_profile_provenance_seams") is True, "existing profile provenance seams must be reused")
    _expect(profile.get("authority") == "research-evidence-and-authoring-context-only", "humanoid profile authority widened")
    _expect(profile.get("constraint_modes") == ["required-range", "hint", "stylization-tolerance"], "humanoid profile constraint modes drifted")
    required_categories = cast(list[object], profile.get("required_categories"))
    _expect(len(required_categories) == 12 and len(set(cast(list[str], required_categories))) == 12, "humanoid profile category set malformed")
    for required in (
        "canonical-body-landmarks",
        "bounded-relative-proportion-ranges",
        "silhouette-critical-identity-features",
        "equipment-anchor-definitions",
        "confidence-and-unknowns",
    ):
        _expect(required in required_categories, f"humanoid profile category missing: {required}")
    _expect(profile.get("is_raster_authority") is False, "humanoid profile cannot become raster authority")

    pose = cast(dict[str, object], contract.get("pose_equipment_constraint"))
    _expect(pose.get("planned_schema") == "tracepixel.humanoid-pose.v1", "humanoid pose schema target drifted")
    _expect(pose.get("binds_profile_digest") is True, "pose intent must bind the humanoid profile digest")
    _expect(pose.get("constraint_modes") == profile.get("constraint_modes"), "pose and humanoid profile constraint modes diverged")
    capabilities = cast(list[object], pose.get("required_capabilities"))
    for required in (
        "named-static-pose-and-orientation-intent",
        "support-and-contact-landmarks",
        "equipment-anchor-identity-and-reference-integrity",
        "attachment-overlap-or-occlusion-intent",
    ):
        _expect(required in capabilities, f"pose/equipment capability missing: {required}")
    _expect(pose.get("equipment_anchor_is_pixel_authority") is False, "equipment anchors cannot become pixel authority")
    _expect(pose.get("is_physics_engine") is False and pose.get("is_inverse_kinematics_solver") is False and pose.get("is_skeletal_raster_authority") is False, "pose contract widened into another engine")

    evidence = cast(dict[str, object], contract.get("evidence_authority"))
    deterministic = cast(list[object], evidence.get("deterministic_facts"))
    perceptual = cast(list[object], evidence.get("perceptual_facts"))
    _expect(len(deterministic) >= 10, "deterministic evidence responsibilities are incomplete")
    for required in ("body-landmark-reference-integrity", "equipment-anchor-reference-integrity", "provider-cost-and-provenance-accounting"):
        _expect(required in deterministic, f"deterministic evidence responsibility missing: {required}")
    for required in ("humanoid-recognizability", "anatomy-believability-for-stylization", "pose-intent-readability", "identity-coherence", "equipment-readability"):
        _expect(required in perceptual, f"perceptual evidence responsibility missing: {required}")
    _expect(evidence.get("vlm_is_deterministic_correctness") is False, "VLM cannot become deterministic truth")
    _expect(evidence.get("final_aesthetic_acceptance") == "human", "final aesthetic acceptance must remain human")

    complexity = cast(dict[str, object], contract.get("complexity"))
    _expect(complexity.get("reuse_existing_single_asset_accounting") is True, "humanoid work must reuse single-asset cost accounting")
    metrics = cast(list[object], complexity.get("required_metrics"))
    for required in ("provider-calls", "input-tokens", "output-tokens", "pixel-edits", "changed-pixels", "wall-time", "failure-category"):
        _expect(required in metrics, f"complexity metric missing: {required}")
    _expect(complexity.get("profile_or_reference_preparation_cost_separately_attributable") is True, "profile/reference cost must remain separately attributable")
    _expect(complexity.get("equipment_or_attachment_context_cost_separately_attributable") is True, "equipment context cost must remain separately attributable")
    _expect(complexity.get("synthetic_quality_cost_winner_allowed") is False, "synthetic quality/cost winner must remain forbidden")
    _expect(complexity.get("b1_single_member_staged_cost_warning_resolved") is False, "G8-H0 cannot claim the B1 staged-cost warning is solved")

    authority = cast(dict[str, object], contract.get("authority"))
    _expect(authority.get("single_asset_pixelprogram_canvas_reused") is True, "existing single-asset raster authority must be reused")
    _expect(authority.get("profile_pose_or_equipment_anchor_becomes_pixel_authority") is False, "profile/pose/equipment anchors cannot become pixel authority")
    _expect(authority.get("second_humanoid_drawing_engine_allowed") is False, "second humanoid drawing engine is forbidden")
    _expect(authority.get("equipment_specific_second_drawing_engine_allowed") is False, "equipment-specific second drawing engine is forbidden")
    _expect(authority.get("skeletal_or_physics_authority_allowed") is False, "skeletal/physics authority is forbidden")
    _expect(authority.get("hidden_humanoid_scheduler_provider_work_allowed") is False, "hidden humanoid scheduler/provider work is forbidden")

    sequencing = cast(dict[str, object], contract.get("sequencing"))
    _expect(sequencing.get("g9_animation") == "blocked-until-g8-static-humanoid-evidence-frozen", "G9 must remain blocked")
    _expect(sequencing.get("p9_trace2d") == "requires-explicit-g10-owner-approval", "P9 must remain behind explicit G10 approval")

    print(json.dumps({
        "schema": "tracepixel.g8-h0-checkpoint.v1",
        "status": "pass",
        "source_issue": 119,
        "current_child": "G8-H0",
        "next_child": "G8-H1",
        "provider_calls": 0,
        "humanoid_raster_generation": 0,
        "animation_authorized": False,
        "trace2d_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
