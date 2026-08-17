from __future__ import annotations

import json
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence" / "p8_b6" / "owner-approved-production-breadth.v1.json"
POSTMORTEM = ROOT / "evidence" / "p8_b6" / "postmortem.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"P8-B6 checkpoint failed: {message}")


def main() -> int:
    evidence = _json(EVIDENCE)
    post = _json(POSTMORTEM)
    lane = _json(CORE_LANE)

    _expect(evidence.get("schema") == "tracepixel.p8-b6-owner-approved-production-breadth.v1", "evidence schema drifted")
    _expect(evidence.get("source_issue") == 92, "owner evidence must remain bound to issue #92")
    _expect(evidence.get("owner_approval_comment_id") == 5321582257, "owner approval identity drifted")
    _expect(evidence.get("owner_verdict") == "accepted", "P8-B5 repaired retained output is not owner-accepted")
    _expect(evidence.get("scope") == "retained-output", "presentation fixtures cannot close P8-B6")

    initial = cast(dict[str, object], evidence.get("initial_authoring"))
    repair = cast(dict[str, object], evidence.get("localized_repair"))
    effective = cast(dict[str, object], evidence.get("effective_attempt_cost"))
    _expect(initial.get("run_id") == 32022902199 and initial.get("artifact_id") == 9286172654, "initial retained run identity drifted")
    _expect(initial.get("artifact_sha256") == "ed618162e9bb1fb7a00cf9031dfe6ae13995e9b3e9b2c28503c311a0ff0860b2", "initial artifact digest drifted")
    _expect(initial.get("member_count") == 8, "expected eight retained production-breadth members")
    _expect(initial.get("deterministic_qa_passed") == 8, "initial deterministic QA count drifted")
    _expect(initial.get("owner_accepted_first_pass") == 7 and initial.get("owner_rejected_first_pass") == 1, "first-pass owner outcome must retain the perceptual rejection")
    _expect(initial.get("declared_max_concurrency") == 2, "initial bounded concurrency drifted")

    _expect(repair.get("run_id") == 32076466054 and repair.get("artifact_id") == 9303644393, "repair retained run identity drifted")
    _expect(repair.get("artifact_sha256") == "e89f393c28988d552c88bcccfb088975025dcd95e4898c768fb2b19a6ff745b1", "repair artifact digest drifted")
    _expect(repair.get("repair_member_id") == "grass-center-b", "repair scope widened beyond owner-rejected member")
    _expect(repair.get("preserved_member_count") == 7, "seven accepted siblings must remain preserved")
    _expect(repair.get("completion_constraint_satisfied") is True, "localized missing-pixel constraint did not pass")
    _expect(repair.get("declared_max_concurrency") == 1, "localized repair must remain single-member bounded")
    _expect(repair.get("prior_png_sha256") != repair.get("replacement_png_sha256"), "rejected PNG was not replaced")

    members = evidence.get("members")
    _expect(type(members) is list and len(cast(list[object], members)) == 8, "final member evidence must contain exactly eight members")
    ids: list[str] = []
    classes: dict[str, int] = {}
    accepted_after_repair = 0
    for raw in cast(list[object], members):
        _expect(type(raw) is dict, "member evidence malformed")
        member = cast(dict[str, object], raw)
        member_id = member.get("member_id")
        asset_class = member.get("asset_class")
        digest = member.get("final_png_sha256")
        verdict = member.get("owner_verdict")
        _expect(type(member_id) is str and member_id not in ids, "member identity duplicated/malformed")
        _expect(type(asset_class) is str, "member asset class malformed")
        _expect(type(digest) is str and len(digest) == 64, "member PNG digest malformed")
        _expect(verdict in ("accepted-first-pass", "accepted-after-localized-repair"), "final member lacks owner acceptance")
        if verdict == "accepted-after-localized-repair":
            accepted_after_repair += 1
            _expect(member_id == "grass-center-b", "only grass-center-b may be accepted after localized repair")
        ids.append(member_id)
        classes[cast(str, asset_class)] = classes.get(cast(str, asset_class), 0) + 1
    _expect(classes == {"item-icon": 2, "scene-prop": 2, "terrain-tile": 4}, "production breadth class counts drifted")
    _expect(accepted_after_repair == 1, "exactly one member should require localized owner repair")

    for metric in ("provider_calls", "input_tokens", "output_tokens", "iterations", "operation_calls", "revisions", "changed_pixels", "pixel_edits", "summed_member_wall_time_ns"):
        left = initial.get(metric)
        right = repair.get(metric)
        total = effective.get(metric)
        _expect(type(left) is int and type(right) is int and type(total) is int, f"cost metric malformed: {metric}")
        _expect(cast(int, left) + cast(int, right) == total, f"effective cost does not reconcile: {metric}")
    _expect(effective.get("provider_calls") == 9, "accepted set must retain the real 8+1 provider-call cost")

    incident = cast(dict[str, object], evidence.get("infrastructure_incident"))
    _expect(incident.get("failed_run_id") == 32036614005 and incident.get("failed_run_attempts") == 3, "bootstrap incident history drifted")
    _expect(incident.get("failure_class") == "github-codeload-http-429", "bootstrap failure classification drifted")
    _expect(incident.get("provider_calls_before_failure") == 0 and incident.get("generated_member_mutations_before_failure") == 0, "bootstrap failure must remain distinct from provider/raster failure")
    _expect(incident.get("resolved_by_successful_run_id") == 32076466054, "bootstrap mitigation has no successful retained run")

    authority = cast(dict[str, object], evidence.get("authority"))
    _expect(authority.get("deterministic_qa_is_perceptual_truth") is False, "deterministic QA cannot absorb perceptual truth")
    _expect(authority.get("owner_visual_acceptance_is_deterministic_qa") is False, "owner acceptance cannot become deterministic QA")
    _expect(authority.get("accepted_sibling_reuse_is_byte_preserving") is True and authority.get("repair_scope_is_member_local") is True, "repair isolation evidence drifted")

    _expect(post.get("schema") == "tracepixel.p8-b6-postmortem.v1" and post.get("status") == "frozen-complete", "postmortem identity/status drifted")
    _expect(post.get("source_issue") == 92 and post.get("owner_approval_comment_id") == 5321582257, "postmortem owner evidence binding drifted")
    scope = cast(dict[str, object], post.get("scope"))
    _expect(scope.get("member_count") == 8 and scope.get("single_asset_authority_reused") is True and scope.get("new_raster_authority_added") is False, "P8 scope conclusion drifted")

    quality = cast(dict[str, object], post.get("quality"))
    _expect(quality.get("initial_deterministic_qa_passed") == 8 and quality.get("initial_owner_rejected") == 1 and quality.get("final_owner_accepted") == 8, "quality accounting drifted")
    _expect(quality.get("localized_repairs") == 1, "quality postmortem lost localized repair")

    cost = cast(dict[str, object], post.get("cost"))
    b1 = cast(dict[str, object], cost.get("b1_carried_forward"))
    _expect([b1.get("tracepixel_vs_raw_input_tokens_mean_ratio"), b1.get("tracepixel_vs_raw_output_tokens_mean_ratio"), b1.get("tracepixel_vs_raw_provider_calls_iterations_mean_ratio"), b1.get("tracepixel_vs_raw_wall_time_mean_ratio")] == [5.06, 4.67, 4.94, 4.58], "B1 staged-cost warning drifted")
    c0 = cast(dict[str, object], cost.get("p8_c0_result"))
    _expect(c0.get("scheduler_provider_calls") == 0 and c0.get("scheduler_input_tokens") == 0 and c0.get("scheduler_output_tokens") == 0, "P8-C0 hidden scheduler cost prohibition drifted")
    real = cast(dict[str, object], cost.get("real_retained_authoring"))
    _expect(real.get("effective_provider_calls") == effective.get("provider_calls") and real.get("effective_input_tokens") == effective.get("input_tokens") and real.get("effective_output_tokens") == effective.get("output_tokens"), "postmortem cost does not match frozen retained evidence")
    _expect(post.get("no_composite_winner") is True and "No synthetic" in cast(str, cost.get("claim_boundary", "")), "P8-B6 must forbid a synthetic composite winner")

    failures = cast(dict[str, object], post.get("failure_behavior"))
    _expect(failures.get("member_local_perceptual_defects") == 1 and failures.get("member_local_repair_successes") == 1, "failure/repair accounting drifted")
    _expect(failures.get("accepted_siblings_regenerated") == 0, "accepted sibling restart amplification regressed")
    _expect(failures.get("bootstrap_infrastructure_failed_attempts") == 3 and failures.get("bootstrap_failures_reached_provider_execution") is False, "infrastructure failure boundary drifted")

    findings = post.get("findings")
    _expect(type(findings) is list and [cast(dict[str, object], item).get("id") for item in cast(list[object], findings)] == ["Q1", "Q2", "C1", "C2", "F1", "F2"], "postmortem finding set drifted")

    post_p8 = cast(dict[str, object], post.get("post_p8"))
    _expect(post_p8.get("g7_simple_creature_direction") == "owner-approved" and post_p8.get("g7_issue") == 109, "G7 post-P8 handoff is not recorded")
    _expect("explicit G10 approval" in cast(str, post_p8.get("p9_trace2d", "")), "P8 must not auto-authorize P9 Trace2D integration")

    _expect(lane.get("current") == "P8" and lane.get("current_child") == "P8-B6" and lane.get("active_issue") == 92, "core lane must point at live P8-B6 while its checkpoint is merged")
    children = cast(dict[str, object], lane.get("child_sequences"))
    p8 = cast(list[object], children.get("P8"))
    _expect(p8[-1] == "P8-B6", "P8-B6 must remain the terminal P8 child")

    print(json.dumps({
        "schema": "tracepixel.p8-b6-checkpoint.v1",
        "member_count": 8,
        "final_owner_accepted": 8,
        "localized_repairs": 1,
        "effective_provider_calls": 9,
        "bootstrap_failed_attempts": 3,
        "no_composite_winner": True,
        "next_authorized_direction": "G7 simple-creature contract lane / issue #109",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
