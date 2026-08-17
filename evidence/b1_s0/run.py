from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
from typing import Mapping, Sequence, cast

from tracepixel.benchmark.b1_adapters import B1CodexExecutor, build_b1_provider_request
from tracepixel.benchmark.b1_harness import (
    B1_EXPECTED_ATTEMPTS,
    B1_FREEZE_COMMIT,
    B1_SCORED_METHOD_IDS,
    assert_b1_is_held_out,
    attempt_relative_path,
    build_b1_schedule,
    load_b1_freeze_record,
    load_b1_preregistration,
)
from tracepixel.benchmark.b1_runner import (
    B1_REQUIRED_PAYLOAD_FILES,
    run_b1_attempt,
    validate_b1_scoring_contract,
    write_b1_attempt_execution,
)

PREREG = Path("evidence/b1/preregistration.v1.json")
FREEZE = Path("evidence/b1/freeze.v1.json")
B0_PREREG = Path("evidence/b0/preregistration.v1.json")
LANE = Path("config/tracepixel.core-lane.json")
RESULTS = Path("evidence/b1/results")
REVIEW = Path("evidence/b1/review")
CLAIM_SCHEMA = "tracepixel.b1-attempt-claim.v1"
SUMMARY_SCHEMA = "tracepixel.b1-scored-cohort-summary.v1"
REVIEW_SCHEMA = "tracepixel.b1-blind-review-package.v1"
SOURCE_PATHS = (
    "src/tracepixel/agent",
    "src/tracepixel/model",
    "src/tracepixel/qa",
    "src/tracepixel/raster",
    "src/tracepixel/repair",
)
METRICS = (
    "input_tokens", "output_tokens", "provider_calls", "tool_calls",
    "operation_calls", "pixel_edits", "visual_observation_calls", "iterations",
    "revisions", "changed_pixels", "repair_cycles", "authored_stages",
    "skipped_stages", "wall_time_ms",
)


def _json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot load {path}: {exc}") from exc
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if check and result.returncode:
        raise SystemExit(f"git {' '.join(args)} failed with exit {result.returncode}")
    return result


def _runner_commit() -> str:
    commit = _git("rev-parse", "HEAD").stdout.strip()
    if len(commit) != 40:
        raise SystemExit("B1-S0 requires a Git checkout with a full HEAD commit")
    return commit


def _source_guard(preregistration: Mapping[str, object]) -> None:
    target = preregistration.get("repository_commit_under_test")
    if type(target) is not str or len(target) != 40:
        raise SystemExit("invalid frozen repository_commit_under_test")
    _git("cat-file", "-e", f"{target}^{{commit}}")
    if _git("diff", "--quiet", target, "--", *SOURCE_PATHS, check=False).returncode:
        raise SystemExit("B1-S0 production Agent/model/QA/raster/repair code differs from the frozen commit")
    if _git("status", "--porcelain", "--untracked-files=all", "--", *SOURCE_PATHS).stdout.strip():
        raise SystemExit("B1-S0 production source paths contain local changes")


def _context(prereg_path: Path, freeze_path: Path, b0_path: Path, lane_path: Path):
    prereg, digest = load_b1_preregistration(prereg_path)
    validate_b1_scoring_contract(prereg)
    if load_b1_freeze_record(freeze_path).get("freeze_commit") != B1_FREEZE_COMMIT:
        raise SystemExit("B1 freeze record drifted")
    assert_b1_is_held_out(prereg, _json(b0_path))
    lane = _json(lane_path)
    if (lane.get("current"), lane.get("current_child"), lane.get("active_issue")) != ("B1", "B1-S0", 79):
        raise SystemExit("B1-S0 requires live lane B1 / B1-S0 / issue #79")
    _source_guard(prereg)
    schedule = build_b1_schedule(prereg, preregistration_sha256=digest)
    attempts = cast(list[object], schedule["attempts"])
    if len(attempts) != B1_EXPECTED_ATTEMPTS:
        raise SystemExit(f"B1-S0 requires exactly {B1_EXPECTED_ATTEMPTS} frozen attempts")
    for identity in attempts:
        build_b1_provider_request(prereg, identity=identity)
    return prereg, schedule, _runner_commit()


def _preflight(prereg, schedule, executor=None):
    first = cast(list[object], schedule["attempts"])[0]
    request = build_b1_provider_request(prereg, identity=first)
    executor = B1CodexExecutor() if executor is None else executor
    preflight = getattr(executor, "preflight", None)
    if not callable(preflight):
        raise SystemExit("B1-S0 executor must provide preflight(request)")
    environment = preflight(request)
    if type(environment) is not dict:
        raise SystemExit("B1-S0 preflight returned invalid environment metadata")
    return executor, cast(dict[str, object], environment)


def _claim_path(root: Path, identity: Mapping[str, object]) -> Path:
    attempt_id = identity.get("attempt_id")
    if type(attempt_id) is not str or not attempt_id:
        raise SystemExit("invalid B1 attempt identity")
    return root / B1_FREEZE_COMMIT / ".claims" / f"{attempt_id}.json"


def _claim(root: Path, identity: Mapping[str, object], runner_commit: str) -> Path:
    path = _claim_path(root, identity)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": CLAIM_SCHEMA, "runner_commit": runner_commit, "identity": dict(identity)}
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise SystemExit(f"existing B1 invocation claim blocks automatic rerun: {path}") from exc
    return path


def _complete_record(directory: Path, identity: Mapping[str, object]) -> dict[str, object]:
    record_path, index_path = directory / "attempt-record.json", directory / "retention-index.json"
    if not record_path.is_file() or not index_path.is_file():
        raise SystemExit(f"incomplete retained B1 attempt blocks safe resume: {directory}")
    record, index = _json(record_path), _json(index_path)
    if record.get("attempt") != identity:
        raise SystemExit(f"retained B1 identity mismatch: {record_path}")
    if index.get("schema") != "tracepixel.b1-retention-index.v1" or index.get("attempt_id") != identity.get("attempt_id"):
        raise SystemExit(f"invalid B1 retention index: {index_path}")
    files = index.get("files")
    if type(files) is not dict or B1_REQUIRED_PAYLOAD_FILES - frozenset(files):
        raise SystemExit(f"incomplete B1 retention index: {index_path}")
    for name, metadata in cast(dict[str, object], files).items():
        if type(name) is not str or Path(name).name != name or name.startswith(".") or type(metadata) is not dict:
            raise SystemExit(f"invalid B1 retention entry: {index_path}")
        payload = (directory / name).read_bytes()
        meta = cast(dict[str, object], metadata)
        if meta.get("bytes") != len(payload) or meta.get("sha256") != sha256(payload).hexdigest():
            raise SystemExit(f"B1 retention payload mismatch: {directory / name}")
    return record


def _reconcile_claims(root: Path, schedule) -> None:
    attempts = cast(list[object], schedule["attempts"])
    scheduled = {cast(dict[str, object], x)["attempt_id"]: cast(dict[str, object], x) for x in attempts}
    claims = root / B1_FREEZE_COMMIT / ".claims"
    if not claims.exists():
        return
    for path in sorted(claims.glob("*.json")):
        claim = _json(path)
        identity = claim.get("identity")
        if claim.get("schema") != CLAIM_SCHEMA or type(identity) is not dict:
            raise SystemExit(f"invalid B1 invocation claim blocks resume: {path}")
        identity = cast(dict[str, object], identity)
        if scheduled.get(identity.get("attempt_id")) != identity:
            raise SystemExit(f"B1 invocation claim is outside the frozen schedule: {path}")
        directory = root / attempt_relative_path(identity)
        if not directory.exists():
            raise SystemExit(f"durable B1 claim without retained result blocks rerun: {path}")
        _complete_record(directory, identity)
        path.unlink()


def _retained(root: Path, schedule) -> list[dict[str, object]]:
    records = []
    for raw in cast(list[object], schedule["attempts"]):
        identity = cast(dict[str, object], raw)
        directory = root / attempt_relative_path(identity)
        if directory.exists():
            records.append(_complete_record(directory, identity))
    return records


def _stable_runner(records, runner_commit: str) -> None:
    commits = set()
    for record in records:
        complexity = record.get("complexity")
        value = cast(dict[str, object], complexity).get("runner_commit") if type(complexity) is dict else None
        if type(value) is not str or len(value) != 40:
            raise SystemExit("retained B1 attempt is missing its exact runner commit")
        commits.add(value)
    if commits and commits != {runner_commit}:
        raise SystemExit(f"B1-S0 runner commit changed after scoring started: retained={sorted(commits)!r}")


def _task_constraints(prereg, task_id: str) -> dict[str, object]:
    for raw in cast(list[object], prereg["tasks"]):
        task = cast(dict[str, object], raw)
        if task.get("id") == task_id:
            return cast(dict[str, object], task["hidden_structural_constraints"])
    raise SystemExit(f"unknown B1 task in retained evidence: {task_id}")


def _structural(prereg, record) -> tuple[int, int, bool]:
    task_id = cast(str, cast(dict[str, object], record["attempt"])["task_id"])
    constraints = _task_constraints(prereg, task_id)
    if record.get("completion") is not True:
        return 0, len(constraints), False
    qa = record.get("deterministic_qa")
    rules = cast(dict[str, object], qa).get("rule_results") if type(qa) is dict else None
    if type(rules) is not dict or set(rules) != set(constraints) or any(type(v) is not bool for v in rules.values()):
        raise SystemExit(f"completed B1 rule results drifted from frozen task: {task_id}")
    passed = sum(v is True for v in rules.values())
    return passed, len(constraints), passed == len(constraints)


def _metric(records, name: str) -> dict[str, object]:
    values = []
    for record in records:
        complexity = record.get("complexity")
        value = cast(dict[str, object], complexity).get(name) if type(complexity) is dict else None
        if type(value) is int:
            values.append(value)
    return {
        "available_count": len(values), "trial_count": len(records),
        "mean": statistics.mean(values) if values else None,
        "median": statistics.median(values) if values else None,
    }


def _stage(records) -> dict[str, object]:
    values = [cast(dict[str, object], r["stage_coverage"]) for r in records if type(r.get("stage_coverage")) is dict and cast(dict[str, object], r["stage_coverage"]).get("applicable") is True]
    if not values:
        return {"applicable": False, "trial_count": len(records)}
    complete = sum(x.get("authoring_complete") is True for x in values)
    return {
        "applicable": True, "trial_count": len(records), "available_count": len(values),
        "authoring_complete_rate": complete / len(values),
        "mean_applied_stages": statistics.mean(cast(int, x["applied_stages"]) for x in values),
        "mean_skipped_stages": statistics.mean(cast(int, x["skipped_stages"]) for x in values),
    }


def _summary(prereg, schedule, records, runner_commit: str) -> dict[str, object]:
    attempts = cast(list[object], schedule["attempts"])
    if len(records) != len(attempts):
        raise SystemExit(f"cannot summarize incomplete B1 cohort: {len(records)}/{len(attempts)}")
    by_id = {cast(dict[str, object], r["attempt"])["attempt_id"]: r for r in records}
    methods = []
    for method_id in B1_SCORED_METHOD_IDS:
        selected = [by_id[cast(dict[str, object], x)["attempt_id"]] for x in attempts if cast(dict[str, object], x)["method_id"] == method_id]
        scored = [r for r in selected if r.get("failure_category") != "void_infrastructure"]
        if not scored:
            raise SystemExit(f"B1 method has no non-void trials: {method_id}")
        fractions, passes, failures = [], 0, Counter()
        for record in scored:
            num, den, all_pass = _structural(prereg, record)
            fractions.append(num / den)
            passes += all_pass
            if type(record.get("failure_category")) is str:
                failures[cast(str, record["failure_category"])] += 1
        methods.append({
            "method_id": method_id,
            "scheduled_trials": len(selected), "non_void_trials": len(scored),
            "void_infrastructure_trials": len(selected) - len(scored),
            "completion_rate": sum(r.get("completion") is True for r in scored) / len(scored),
            "structural_pass_rate": passes / len(scored),
            "mean_structural_fraction": statistics.mean(fractions),
            "failure_counts": dict(sorted(failures.items())),
            "stage_coverage": _stage(scored),
            "complexity": {name: _metric(scored, name) for name in METRICS},
        })
    return {
        "schema": SUMMARY_SCHEMA, "benchmark_id": "B1", "freeze_commit": B1_FREEZE_COMMIT,
        "repository_commit_under_test": prereg["repository_commit_under_test"],
        "runner_commit": runner_commit, "scheduled_attempt_count": len(attempts),
        "retained_attempt_count": len(records),
        "void_infrastructure_count": sum(r.get("failure_category") == "void_infrastructure" for r in records),
        "methods": methods, "human_review_status": "pending",
        "claim_boundary": "held-out post-P7 generalization diagnostic; no composite winner; owner blind review pending",
    }


def _blind_key(identity: Mapping[str, object]) -> str:
    return sha256(f"{identity['task_id']}|{identity['trial_index']}|{identity['method_id']}".encode()).hexdigest()


def _blind_review(prereg, root: Path, review_root: Path, schedule, records) -> dict[str, object]:
    target = review_root / B1_FREEZE_COMMIT
    if target.exists():
        raise SystemExit(f"refusing to overwrite B1 blind review package: {target}")
    target.mkdir(parents=True)
    by_id = {cast(dict[str, object], r["attempt"])["attempt_id"]: r for r in records}
    grouped: dict[str, list[tuple[str, dict[str, object]]]] = {}
    for raw in cast(list[object], schedule["attempts"]):
        identity = cast(dict[str, object], raw)
        if by_id[identity["attempt_id"]].get("completion") is True:
            grouped.setdefault(cast(str, identity["task_id"]), []).append((_blind_key(identity), identity))
    entries = []
    for task_id in sorted(grouped):
        task_dir = target / task_id
        task_dir.mkdir()
        for rank, (key, identity) in enumerate(sorted(grouped[task_id]), start=1):
            source = root / attempt_relative_path(identity) / "preview-8x.png"
            if not source.is_file():
                raise SystemExit(f"completed B1 attempt lacks preview: {source}")
            destination = task_dir / f"{rank:02d}-{key[:16]}.png"
            shutil.copyfile(source, destination)
            entries.append({
                "review_id": key, "task_id": task_id, "trial_index": identity["trial_index"],
                "order": rank, "preview": destination.relative_to(target).as_posix(),
            })
    perceptual = cast(dict[str, object], prereg["perceptual_evaluation"])
    manifest = {
        "schema": REVIEW_SCHEMA, "freeze_commit": B1_FREEZE_COMMIT,
        "ordering": perceptual["blind_order"], "method_labels_exposed": False,
        "dimensions": perceptual["dimensions"], "scale": perceptual["scale"], "entries": entries,
    }
    (target / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return manifest


def preflight_cohort(prereg=PREREG, freeze=FREEZE, b0=B0_PREREG, lane=LANE, *, executor=None):
    preregistration, schedule, runner_commit = _context(prereg, freeze, b0, lane)
    _, environment = _preflight(preregistration, schedule, executor)
    return {
        "schema": "tracepixel.b1-scored-cohort-preflight.v1", "benchmark_id": "B1",
        "freeze_commit": B1_FREEZE_COMMIT,
        "repository_commit_under_test": preregistration["repository_commit_under_test"],
        "runner_commit": runner_commit, "scheduled_attempt_count": schedule["scheduled_attempt_count"],
        "provider_environment": environment, "provider_invoked": False, "scored_attempts_written": False,
    }


def run_cohort(prereg=PREREG, freeze=FREEZE, b0=B0_PREREG, lane=LANE, results=RESULTS, review=REVIEW, *, executor=None):
    preregistration, schedule, runner_commit = _context(prereg, freeze, b0, lane)
    _reconcile_claims(results, schedule)
    records = _retained(results, schedule)
    _stable_runner(records, runner_commit)
    executor, environment = _preflight(preregistration, schedule, executor)
    retained_ids = {cast(dict[str, object], r["attempt"])["attempt_id"] for r in records}
    for raw in cast(list[object], schedule["attempts"]):
        identity = cast(dict[str, object], raw)
        if identity["attempt_id"] in retained_ids:
            continue
        claim = _claim(results, identity, runner_commit)
        execution = run_b1_attempt(preregistration, identity=identity, executor=executor, runner_commit=runner_commit)
        write_b1_attempt_execution(results, preregistration, execution)
        claim.unlink()
    records = _retained(results, schedule)
    summary = _summary(preregistration, schedule, records, runner_commit)
    summary["provider_environment"] = environment
    summary_path = results / B1_FREEZE_COMMIT / "cohort-summary.json"
    if summary_path.exists():
        raise SystemExit(f"refusing to overwrite B1 cohort summary: {summary_path}")
    review_manifest = _blind_review(preregistration, results, review, schedule, records)
    summary["blind_review_entry_count"] = len(cast(list[object], review_manifest["entries"]))
    summary_path.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return summary


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Preflight or run the frozen owner-local B1-S0 scored cohort.")
    parser.add_argument("--preregistration", type=Path, default=PREREG)
    parser.add_argument("--freeze-record", type=Path, default=FREEZE)
    parser.add_argument("--b0-preregistration", type=Path, default=B0_PREREG)
    parser.add_argument("--core-lane", type=Path, default=LANE)
    parser.add_argument("--results-root", type=Path, default=RESULTS)
    parser.add_argument("--review-root", type=Path, default=REVIEW)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--run-scored-cohort", action="store_true")
    args = parser.parse_args(argv)
    if args.preflight_only:
        result = preflight_cohort(args.preregistration, args.freeze_record, args.b0_preregistration, args.core_lane)
    else:
        result = run_cohort(
            args.preregistration, args.freeze_record, args.b0_preregistration, args.core_lane,
            args.results_root, args.review_root,
        )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
