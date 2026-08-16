from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping, Sequence, cast

FREEZE = "c4b31288867fd4c4cf5ea3664808bd6f47cca1db"
METHODS = ("tracepixel-staged-v1", "raw-pixel-program-v1")
DIMS = ("recognizability", "readability_at_native_1x", "style_coherence")
RESULTS = Path("evidence/b0/results") / FREEZE / "cohort-summary.json"
REVIEW_ROOT = Path("evidence/b0/review") / FREEZE
REVIEW_MANIFEST = REVIEW_ROOT / "manifest.json"
OWNER_REVIEW = REVIEW_ROOT / "owner-review.json"
OWNER_SUMMARY = REVIEW_ROOT / "owner-review-summary.json"
POSTMORTEM = Path("evidence/b0/postmortem.v1.json")
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


def _unblind(review_id: str, task_id: str, trial_index: int) -> str:
    matches = [
        method
        for method in METHODS
        if sha256(f"{task_id}|{trial_index}|{method}".encode("utf-8")).hexdigest() == review_id
    ]
    if len(matches) != 1:
        raise CheckpointError(f"cannot unblind review id: {review_id}")
    return matches[0]


def _derive_owner_summary(owner: Mapping[str, object]) -> dict[str, object]:
    raw_ratings = owner.get("ratings")
    if type(raw_ratings) is not list or len(raw_ratings) != 28:
        raise CheckpointError("owner review must contain 28 ratings")
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for raw in cast(list[object], raw_ratings):
        if type(raw) is not dict:
            raise CheckpointError("invalid owner rating")
        rating = cast(dict[str, object], raw)
        review_id, task_id, trial_index = rating.get("review_id"), rating.get("task_id"), rating.get("trial_index")
        if type(review_id) is not str or type(task_id) is not str or type(trial_index) is not int:
            raise CheckpointError("invalid owner rating identity")
        for dim in DIMS:
            score = rating.get(dim)
            if type(score) is not int or not 1 <= score <= 5:
                raise CheckpointError(f"invalid owner rating score: {dim}")
        if type(rating.get("human_rejection")) is not bool:
            raise CheckpointError("human_rejection must be boolean")
        grouped[_unblind(review_id, task_id, trial_index)].append(rating)
    methods = []
    for method_id in sorted(grouped):
        selected = grouped[method_id]
        methods.append({
            "method_id": method_id,
            "rated_artifacts": len(selected),
            "human_rejection_count": sum(item["human_rejection"] is True for item in selected),
            "mean": {dim: sum(cast(int, item[dim]) for item in selected) / len(selected) for dim in DIMS},
        })
    return {
        "schema": "tracepixel.b0-owner-review-summary.v1",
        "freeze_commit": FREEZE,
        "rating_count": 28,
        "methods": methods,
        "claim_boundary": "human perception only; deterministic correctness remains separate; no composite winner",
    }


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise CheckpointError(message)


def _validate_post_b0_lane(lane: Mapping[str, object]) -> None:
    sequence = lane.get("sequence")
    current = lane.get("current")
    _expect(type(sequence) is list and type(current) is str, "core lane sequence/current malformed")
    phases = cast(list[object], sequence)
    _expect(all(type(item) is str for item in phases), "core lane sequence must contain strings")
    phase_names = cast(list[str], phases)
    _expect("P7" in phase_names and current in phase_names, "core lane must retain P7 and a known current phase")
    _expect(
        phase_names.index(cast(str, current)) >= phase_names.index("P7"),
        "core lane must remain at or beyond the P7 handoff after frozen B0-P0",
    )

    if current == "P7":
        child_sequences = lane.get("child_sequences")
        _expect(type(child_sequences) is dict, "core lane child_sequences malformed")
        p7_children = cast(dict[str, object], child_sequences).get("P7")
        current_child = lane.get("current_child")
        _expect(
            type(p7_children) is list and current_child in cast(list[object], p7_children),
            "active P7 child must be one of the declared P7 children",
        )
        _expect(lane.get("active_issue") == 71, "active P7 work must remain on issue #71")


def run() -> dict[str, object]:
    cohort = _load(RESULTS)
    manifest = _load(REVIEW_MANIFEST)
    owner = _load(OWNER_REVIEW)
    owner_summary = _load(OWNER_SUMMARY)
    post = _load(POSTMORTEM)
    lane = _load(CORE_LANE)

    _expect(post.get("schema") == "tracepixel.b0-postmortem.v1", "postmortem schema mismatch")
    _expect(post.get("benchmark_id") == "B0" and post.get("status") == "frozen-complete", "postmortem identity/status mismatch")
    _expect(post.get("freeze_commit") == FREEZE == cohort.get("freeze_commit") == manifest.get("freeze_commit") == owner.get("freeze_commit"), "freeze mismatch")
    _expect(post.get("repository_commit_under_test") == cohort.get("repository_commit_under_test"), "repository commit mismatch")
    _expect(post.get("runner_commit") == cohort.get("runner_commit"), "runner commit mismatch")

    source = cast(dict[str, object], post.get("source_evidence"))
    _expect(source.get("blind_review_manifest_sha256") == _sha(REVIEW_MANIFEST) == owner.get("review_manifest_sha256"), "blind review manifest hash mismatch")
    _expect(source.get("owner_review_sha256") == _sha(OWNER_REVIEW), "owner review hash mismatch")
    _expect(source.get("owner_review_summary_sha256") == _sha(OWNER_SUMMARY), "owner review summary hash mismatch")

    derived = _derive_owner_summary(owner)
    _expect(owner_summary == derived, "owner review summary is not derived exactly from sealed ratings")

    post_cohort = cast(dict[str, object], post.get("cohort"))
    _expect(post_cohort.get("scheduled_attempts") == cohort.get("scheduled_attempt_count") == 28, "scheduled attempt count mismatch")
    _expect(post_cohort.get("retained_attempts") == cohort.get("retained_attempt_count") == 28, "retained attempt count mismatch")
    _expect(post_cohort.get("void_infrastructure") == cohort.get("void_infrastructure_count") == 0, "void count mismatch")

    source_methods = _method_map(cohort.get("methods"), "cohort.methods")
    post_methods = _method_map(post_cohort.get("methods"), "postmortem.cohort.methods")
    _expect(set(source_methods) == set(post_methods) == set(METHODS), "cohort method set mismatch")
    complexity_map = {
        "input_tokens_mean": "input_tokens",
        "output_tokens_mean": "output_tokens",
        "iterations_mean": "iterations",
        "revisions_mean": "revisions",
        "operation_calls_mean": "operation_calls",
        "changed_pixels_mean": "changed_pixels",
        "wall_time_ms_mean": "wall_time_ms",
    }
    for method_id in METHODS:
        src, dst = source_methods[method_id], post_methods[method_id]
        for key in ("scheduled_trials", "completion_rate", "structural_pass_rate", "mean_structural_fraction"):
            _expect(dst.get(key) == src.get(key), f"{method_id} {key} mismatch")
        src_complexity = cast(dict[str, object], src.get("complexity"))
        dst_complexity = cast(dict[str, object], dst.get("complexity"))
        for dst_key, src_key in complexity_map.items():
            metric = cast(dict[str, object], src_complexity.get(src_key))
            _expect(dst_complexity.get(dst_key) == metric.get("mean"), f"{method_id} complexity mismatch: {dst_key}")

    perceptual = cast(dict[str, object], post.get("perceptual"))
    _expect(perceptual.get("rating_count") == owner_summary.get("rating_count") == 28, "perceptual rating count mismatch")
    _expect(_method_map(perceptual.get("methods"), "postmortem.perceptual.methods") == _method_map(owner_summary.get("methods"), "owner-summary.methods"), "perceptual method summary mismatch")

    expected_rejections: dict[str, int] = defaultdict(int)
    for raw in cast(list[object], owner["ratings"]):
        rating = cast(dict[str, object], raw)
        if rating["human_rejection"] is True and _unblind(cast(str, rating["review_id"]), cast(str, rating["task_id"]), cast(int, rating["trial_index"])) == "tracepixel-staged-v1":
            expected_rejections[cast(str, rating["task_id"])] += 1
    _expect(perceptual.get("tracepixel_human_rejections_by_task") == dict(expected_rejections), "per-task staged rejection classification mismatch")

    failures = cast(dict[str, object], post.get("failure_classification"))
    _expect(failures.get("provider_or_execution_failures") == 0, "unexpected provider/execution failure count")
    _expect(failures.get("infrastructure_voids") == 0, "unexpected infrastructure void count")
    _expect(failures.get("deterministic_structural_failures_at_completion") == 0, "unexpected deterministic completion failure count")
    _expect(failures.get("human_rejections") == 5 and failures.get("human_rejections_are_perceptual_not_deterministic") is True, "human rejection classification mismatch")

    followups = post.get("architecture_followups")
    _expect(type(followups) is list and [cast(dict[str, object], item).get("id") for item in cast(list[object], followups)] == ["A1", "A2", "A3", "A4", "A5"], "architecture follow-ups mismatch")
    _expect(post.get("owner_gates_crossed") == [], "B0-P0 must not silently cross an owner gate")
    _expect("no composite winner" in cast(str, post.get("claim_boundary", "")), "claim boundary must forbid a composite winner")

    _validate_post_b0_lane(lane)

    return {
        "schema": "tracepixel.b0-p0-checkpoint.v1",
        "freeze_commit": FREEZE,
        "scheduled_attempts": 28,
        "retained_attempts": 28,
        "owner_ratings": 28,
        "human_rejections": 5,
        "next": "P7-F0",
    }


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    try:
        print(json.dumps(run(), sort_keys=True))
        return 0
    except (CheckpointError, OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
        raise SystemExit(f"B0-P0 checkpoint failed: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
