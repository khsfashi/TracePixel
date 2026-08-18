from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from evidence.p10_c4.forward_checkpoint import main as c4_forward_main

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence" / "p10_c5" / "owner-approved-simple-creature.v1.json"
POSTMORTEM = ROOT / "evidence" / "p10_c5" / "postmortem.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"P10-C5 checkpoint failed: {message}")


def main() -> int:
    _expect(c4_forward_main() == 0, "P10-C4 historical checkpoint failed")

    evidence = _json(EVIDENCE)
    post = _json(POSTMORTEM)
    lane = _json(CORE_LANE)

    _expect(evidence.get("schema") == "tracepixel.p10-c5-owner-approved-simple-creature.v1", "owner evidence schema drifted")
    _expect(evidence.get("source_issue") == 109, "owner evidence must stay bound to issue #109")
    _expect(evidence.get("owner_approval_comment_id") == 5323810558, "owner approval identity drifted")
    _expect(evidence.get("owner_verdict") == "accepted", "owner verdict is not accepted")
    _expect(evidence.get("scope") == "retained-output", "C5 must approve retained output, not a presentation fixture")

    retained = cast(dict[str, object], evidence.get("retained_authoring"))
    _expect(retained.get("run_id") == 32099831527 and retained.get("artifact_id") == 9311214420, "retained run/artifact identity drifted")
    _expect(retained.get("main_sha") == "d736281c71c4a9a65ca44a0fd4202d994241decf", "retained main SHA drifted")
    _expect(retained.get("final_png_sha256") == "1ce31cd4fdeeb3d19403a44e074dc6e32803870ae30c40fccaefc96582eb4532", "retained PNG digest drifted")
    _expect(retained.get("canvas_width") == 32 and retained.get("canvas_height") == 32, "retained canvas dimensions drifted")
    _expect(retained.get("provider_calls") == 1, "accepted retained attempt must preserve one real provider call")
    _expect(retained.get("input_tokens") == 18854 and retained.get("output_tokens") == 3762, "retained token accounting drifted")
    _expect(retained.get("operation_calls") == 1 and retained.get("pixel_edits") == 270 and retained.get("changed_pixels") == 270, "retained edit accounting drifted")
    _expect(retained.get("final_deterministic_qa_findings") == 0, "final deterministic QA is not clean")
    _expect(retained.get("canvas_restarts") == 0 and retained.get("regeneration_provider_calls") == 0, "accepted attempt unexpectedly restarted/regenerated")
    _expect(retained.get("scheduler_provider_calls") == 0 and retained.get("morphology_research_provider_calls") == 0, "hidden provider work appeared")
    _expect(retained.get("retained_morphology_reused") is True and retained.get("retained_pose_reused") is True, "retained morphology/pose reuse drifted")
    _expect(retained.get("new_raster_authority_added") is False, "P10 added a second raster authority")

    perceptual = cast(dict[str, object], evidence.get("perceptual_review"))
    _expect(perceptual.get("recognizability") == "accepted-generic-simple-creature", "generic creature recognizability was not accepted")
    for key in ("native_1x_readability", "silhouette_pose_readability", "stylized_anatomy", "visual_coherence"):
        _expect(perceptual.get(key) == "accepted", f"perceptual criterion not accepted: {key}")
    _expect(perceptual.get("species_specific_recognition") == "not-required-for-synthetic-fixture", "synthetic fixture was incorrectly turned into a named-species test")
    subject = cast(dict[str, object], perceptual.get("synthetic_subject_identity"))
    _expect([subject.get("family_id"), subject.get("species_id"), subject.get("form_id")] == ["fixture-family", "fixture-species", "fixture-form"], "synthetic subject identity drifted")

    authority = cast(dict[str, object], evidence.get("authority"))
    for key in ("owner_visual_acceptance_is_deterministic_qa", "recognizability_is_deterministic_truth", "pose_readability_is_deterministic_truth", "stylized_anatomy_is_deterministic_truth", "visual_coherence_is_deterministic_truth"):
        _expect(authority.get(key) is False, f"perceptual authority boundary regressed: {key}")
    _expect(authority.get("pixelprogram_canvas_remain_raster_authority") is True, "PixelProgram/Canvas authority drifted")

    _expect(post.get("schema") == "tracepixel.p10-c5-postmortem.v1" and post.get("status") == "frozen-complete", "postmortem identity/status drifted")
    _expect(post.get("source_issue") == 109 and post.get("owner_approval_comment_id") == 5323810558, "postmortem owner binding drifted")
    scope = cast(dict[str, object], post.get("scope"))
    _expect(scope.get("promotion") == "simple-creature" and scope.get("single_asset_authority_reused") is True, "promotion scope drifted")
    _expect(scope.get("new_raster_authority_added") is False and scope.get("humanoid_implementation_added") is False and scope.get("animation_implementation_added") is False and scope.get("trace2d_integration_added") is False, "P10 scope widened during C5")

    quality = cast(dict[str, object], post.get("quality"))
    _expect(quality.get("deterministic_qa_final_findings") == 0 and quality.get("owner_verdict") == "accepted", "quality conclusion drifted")
    _expect(quality.get("recognizable_as_generic_simple_creature") is True and quality.get("pose_readable") is True and quality.get("tail_readable") is True, "owner visual findings drifted")
    _expect(quality.get("named_real_species_required") is False, "postmortem incorrectly requires named real-species recognition")

    cost = cast(dict[str, object], post.get("cost"))
    _expect([cost.get("provider_calls"), cost.get("input_tokens"), cost.get("output_tokens"), cost.get("operation_calls"), cost.get("pixel_edits"), cost.get("changed_pixels")] == [1, 18854, 3762, 1, 270, 270], "postmortem cost accounting drifted")
    _expect(cost.get("regeneration_provider_calls") == 0 and cost.get("scheduler_provider_calls") == 0 and cost.get("morphology_research_provider_calls") == 0, "postmortem hides additional provider work")
    _expect(cost.get("b1_staged_single_asset_cost_warning") == "carried-forward-unresolved", "B1 staged-cost warning was erased")

    failures = cast(dict[str, object], post.get("failure_behavior"))
    _expect(failures.get("deterministic_final_failures") == 0 and failures.get("owner_rejected_retained_outputs") == 0 and failures.get("repair_attempts") == 0 and failures.get("canvas_restarts") == 0, "failure behavior drifted")

    findings = post.get("findings")
    _expect(type(findings) is list and [cast(dict[str, object], item).get("id") for item in cast(list[object], findings)] == ["Q1", "Q2", "C1", "C2", "F1", "A1"], "postmortem finding set drifted")

    post_p10 = cast(dict[str, object], post.get("post_p10"))
    _expect(post_p10.get("g8_humanoid_direction") == "owner-approved-long-term-destination-contract-lane-next", "G8 sequential handoff drifted")
    _expect(post_p10.get("g9_animation_direction") == "blocked-until-humanoid-promotion-evidence", "G9 advanced before humanoid evidence")
    _expect("explicit G10 approval" in cast(str, post_p10.get("p9_trace2d", "")), "P10 must not auto-authorize Trace2D integration")

    _expect(lane.get("current") == "P10" and lane.get("current_child") == "P10-C5" and lane.get("active_issue") == 109, "core lane must point at live P10-C5")
    children = cast(dict[str, object], lane.get("child_sequences"))
    p10 = cast(list[object], children.get("P10"))
    _expect(p10[-1] == "P10-C5", "P10-C5 must remain terminal P10 child")

    print(json.dumps({
        "schema": "tracepixel.p10-c5-checkpoint.v1",
        "status": "pass",
        "owner_verdict": "accepted",
        "retained_run_id": 32099831527,
        "provider_calls": 1,
        "input_tokens": 18854,
        "output_tokens": 3762,
        "repairs": 0,
        "next_authorized_direction": "G8 humanoid promotion contract lane",
        "trace2d_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
