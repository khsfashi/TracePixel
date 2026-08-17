from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping, Sequence, cast

from evidence.b1_s0.review import load_review_manifest, owner_review_summary, validate_owner_review

FREEZE = "ca612a026ff5e74c397d9aa4ef8c0bdb25d1df6a"
METHODS = ("tracepixel-post-p7-v1", "raw-pixel-program-v1")
RESULTS = Path("evidence/b1/results") / FREEZE / "cohort-summary.json"
REVIEW_ROOT = Path("evidence/b1/review") / FREEZE
OWNER_REVIEW = REVIEW_ROOT / "owner-review.json"
OWNER_SUMMARY = REVIEW_ROOT / "owner-review-summary.json"
POSTMORTEM = Path("evidence/b1/postmortem.v1.json")
CORE_LANE = Path("config/tracepixel.core-lane.json")


class CheckpointError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise CheckpointError(f"expected object: {path}")
    return cast(dict[str, object], value)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise CheckpointError(message)


def _method_map(items: object, label: str) -> dict[str, dict[str, object]]:
    if type(items) is not list:
        raise CheckpointError(f"{label} must be a list")
    out: dict[str, dict[str, object]] = {}
    for raw in cast(list[object], items):
        if type(raw) is not dict:
            raise CheckpointError(f"{label} contains non-object")
        item = cast(dict[str, object], raw)
        method_id = item.get("method_id")
        if type(method_id) is not str or method_id in out:
            raise CheckpointError(f"invalid/duplicate method in {label}")
        out[method_id] = item
    return out


def _metric_mean(method: Mapping[str, object], name: str) -> object:
    complexity = method.get("complexity")
    if type(complexity) is not dict:
        raise CheckpointError(f"missing complexity: {name}")
    metric = cast(dict[str, object], complexity).get(name)
    if type(metric) is not dict:
        raise CheckpointError(f"missing complexity metric: {name}")
    return cast(dict[str, object], metric).get("mean")


def run() -> dict[str, object]:
    cohort = _load(RESULTS)
    owner = _load(OWNER_REVIEW)
    owner_summary = _load(OWNER_SUMMARY)
    post = _load(POSTMORTEM)
    lane = _load(CORE_LANE)
    manifest, manifest_sha = load_review_manifest(Path("evidence/b1/review"))

    _expect(post.get("schema") == "tracepixel.b1-postmortem.v1", "postmortem schema mismatch")
    _expect(post.get("benchmark_id") == "B1" and post.get("status") == "frozen-complete", "postmortem identity/status mismatch")
    _expect(post.get("freeze_commit") == FREEZE == cohort.get("freeze_commit") == owner.get("freeze_commit"), "freeze mismatch")
    _expect(post.get("repository_commit_under_test") == cohort.get("repository_commit_under_test"), "repository commit mismatch")
    _expect(post.get("runner_commit") == cohort.get("runner_commit"), "runner commit mismatch")

    source = post.get("source_evidence")
    _expect(type(source) is dict, "source_evidence malformed")
    source_map = cast(dict[str, object], source)
    _expect(source_map.get("blind_review_manifest_sha256") == manifest_sha == owner.get("review_manifest_sha256"), "blind manifest hash mismatch")
    _expect(source_map.get("owner_review_sha256") == _sha(OWNER_REVIEW), "owner review hash mismatch")
    _expect(source_map.get("owner_review_summary_sha256") == _sha(OWNER_SUMMARY), "owner review summary hash mismatch")

    ratings, unblinded = validate_owner_review(owner, manifest, manifest_sha)
    derived_owner_summary = owner_review_summary(ratings, unblinded)
    _expect(owner_summary == derived_owner_summary, "owner summary is not exactly derived from sealed ratings")

    post_cohort = post.get("cohort")
    _expect(type(post_cohort) is dict, "postmortem cohort malformed")
    post_cohort_map = cast(dict[str, object], post_cohort)
    _expect(post_cohort_map.get("scheduled_attempts") == cohort.get("scheduled_attempt_count") == 28, "scheduled attempt mismatch")
    _expect(post_cohort_map.get("retained_attempts") == cohort.get("retained_attempt_count") == 28, "retained attempt mismatch")
    _expect(post_cohort_map.get("void_infrastructure") == cohort.get("void_infrastructure_count") == 0, "void count mismatch")

    source_methods = _method_map(cohort.get("methods"), "cohort.methods")
    post_methods = _method_map(post_cohort_map.get("methods"), "postmortem.cohort.methods")
    _expect(set(source_methods) == set(post_methods) == set(METHODS), "method set mismatch")
    complexity_fields = {
        "input_tokens_mean": "input_tokens",
        "output_tokens_mean": "output_tokens",
        "provider_calls_mean": "provider_calls",
        "iterations_mean": "iterations",
        "revisions_mean": "revisions",
        "operation_calls_mean": "operation_calls",
        "changed_pixels_mean": "changed_pixels",
        "pixel_edits_mean": "pixel_edits",
        "repair_cycles_mean": "repair_cycles",
        "wall_time_ms_mean": "wall_time_ms",
    }
    for method_id in METHODS:
        src, dst = source_methods[method_id], post_methods[method_id]
        for key in ("scheduled_trials", "completion_rate", "structural_pass_rate", "mean_structural_fraction"):
            _expect(dst.get(key) == src.get(key), f"{method_id} {key} mismatch")
        dst_complexity = dst.get("complexity")
        _expect(type(dst_complexity) is dict, f"{method_id} postmortem complexity malformed")
        for dst_key, src_key in complexity_fields.items():
            _expect(cast(dict[str, object], dst_complexity).get(dst_key) == _metric_mean(src, src_key), f"{method_id} complexity mismatch: {dst_key}")

    trace_source = source_methods["tracepixel-post-p7-v1"]
    stage = trace_source.get("stage_coverage")
    _expect(type(stage) is dict, "TracePixel stage coverage missing")
    stage_map = cast(dict[str, object], stage)
    _expect(stage_map.get("authoring_complete_rate") == 1.0, "TracePixel required stage completion regressed")
    _expect(stage_map.get("mean_applied_stages") == 6 and stage_map.get("mean_skipped_stages") == 0, "TracePixel six-stage traversal mismatch")
    _expect(_metric_mean(trace_source, "repair_cycles") == 0, "B1 unexpectedly exercised scored repair cycles")

    perceptual = post.get("perceptual")
    _expect(type(perceptual) is dict, "postmortem perceptual malformed")
    perceptual_map = cast(dict[str, object], perceptual)
    _expect(perceptual_map.get("rating_count") == owner_summary.get("rating_count") == 28, "rating count mismatch")
    _expect(_method_map(perceptual_map.get("methods"), "postmortem.perceptual.methods") == _method_map(owner_summary.get("methods"), "owner-summary.methods"), "perceptual summary mismatch")

    owner_methods = _method_map(owner_summary.get("methods"), "owner-summary.methods")
    raw_owner = owner_methods["raw-pixel-program-v1"]
    trace_owner = owner_methods["tracepixel-post-p7-v1"]
    _expect(raw_owner.get("human_rejection_count") == 1 and trace_owner.get("human_rejection_count") == 0, "human rejection counts mismatch")
    _expect(cast(dict[str, object], raw_owner["mean"]).get("recognizability") == cast(dict[str, object], trace_owner["mean"]).get("recognizability") == 4.0, "recognizability parity mismatch")

    failures = post.get("failure_classification")
    _expect(type(failures) is dict, "failure classification malformed")
    failure_map = cast(dict[str, object], failures)
    _expect(failure_map.get("provider_or_execution_failures") == 0, "unexpected provider/execution failures")
    _expect(failure_map.get("infrastructure_voids") == 0, "unexpected infrastructure voids")
    _expect(failure_map.get("deterministic_structural_failures_at_completion") == 0, "unexpected deterministic completion failures")
    _expect(failure_map.get("human_rejections") == 1 and failure_map.get("human_rejections_are_perceptual_not_deterministic") is True, "human rejection classification mismatch")

    findings = post.get("generalization_findings")
    _expect(type(findings) is list and [cast(dict[str, object], item).get("id") for item in cast(list[object], findings)] == ["D1", "D2", "D3", "D4"], "generalization findings mismatch")
    followups = post.get("architecture_followups")
    _expect(type(followups) is list and [cast(dict[str, object], item).get("id") for item in cast(list[object], followups)] == ["A1", "A2", "A3", "A4", "A5"], "architecture follow-ups mismatch")
    _expect("no composite winner" in cast(str, post.get("claim_boundary", "")), "claim boundary must forbid a composite winner")

    gates = post.get("owner_gates_crossed")
    _expect(type(gates) is list and len(cast(list[object], gates)) == 1, "B1 must record exactly the explicitly activated G6 gate")
    gate = cast(dict[str, object], cast(list[object], gates)[0])
    _expect(cast(str, gate.get("gate", "")).startswith("G6 "), "B1 owner gate record must be G6")

    _expect(lane.get("current") == "P8", "B1-P0 must hand off to P8")
    child_sequences = lane.get("child_sequences")
    _expect(type(child_sequences) is dict, "P8 child sequence missing after B1 handoff")
    p8_children = cast(dict[str, object], child_sequences).get("P8")
    current_child = lane.get("current_child")
    _expect(type(p8_children) is list and current_child in cast(list[object], p8_children), "active P8 child must be declared")
    child_names = cast(list[str], p8_children)
    _expect(child_names.index(cast(str, current_child)) >= child_names.index("P8-X0"), "core lane regressed before the frozen B1 -> P8-X0 handoff")
    _expect(lane.get("active_issue") == 92, "P8 handoff must target issue #92")

    return {
        "schema": "tracepixel.b1-p0-checkpoint.v1",
        "freeze_commit": FREEZE,
        "scheduled_attempts": 28,
        "retained_attempts": 28,
        "owner_ratings": 28,
        "tracepixel_human_rejections": 0,
        "raw_human_rejections": 1,
        "tracepixel_repair_cycles_mean": 0,
        "next": "P8-X0",
    }


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    try:
        print(json.dumps(run(), sort_keys=True))
        return 0
    except (CheckpointError, OSError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
        raise SystemExit(f"B1-P0 checkpoint failed: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
