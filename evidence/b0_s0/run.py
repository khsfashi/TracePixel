from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import statistics
import subprocess
from typing import Mapping, Sequence, cast

from tracepixel.benchmark import (
    B0_FREEZE_COMMIT,
    B0CodexExecutor,
    attempt_relative_path,
    blind_review_key,
    build_b0_provider_request,
    build_b0_schedule,
    json_payload,
    load_b0_preregistration,
    run_b0_attempt,
    validate_b0_scoring_contract,
    write_attempt_record,
)

DEFAULT_PREREGISTRATION = Path("evidence/b0/preregistration.v1.json")
DEFAULT_RESULTS_ROOT = Path("evidence/b0/results")
DEFAULT_REVIEW_ROOT = Path("evidence/b0/review")
SUMMARY_SCHEMA_V1 = "tracepixel.b0-scored-cohort-summary.v1"
BLIND_REVIEW_SCHEMA_V1 = "tracepixel.b0-blind-review-package.v1"
_PRODUCTION_PATHS = (
    "src/tracepixel/agent",
    "src/tracepixel/model",
    "src/tracepixel/qa",
    "src/tracepixel/raster",
)
_COMPLEXITY_FIELDS = (
    "input_tokens",
    "output_tokens",
    "tool_calls",
    "operation_calls",
    "iterations",
    "revisions",
    "changed_pixels",
    "wall_time_ms",
)


def _git(arguments: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *arguments], capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(arguments)} failed with exit {result.returncode}")
    return result


def _runner_commit() -> str:
    value = _git(("rev-parse", "HEAD")).stdout.strip()
    if len(value) != 40:
        raise SystemExit("B0-S0 must run from a Git checkout with a full HEAD commit")
    return value


def _verify_source_boundary(preregistration: Mapping[str, object]) -> None:
    target = preregistration.get("repository_commit_under_test")
    if type(target) is not str or len(target) != 40:
        raise SystemExit("frozen repository_commit_under_test is invalid")
    _git(("cat-file", "-e", f"{target}^{{commit}}"))
    diff = _git(("diff", "--quiet", target, "--", *_PRODUCTION_PATHS), check=False)
    if diff.returncode != 0:
        raise SystemExit(
            "B0-S0 refused to start: production Agent/model/QA/raster code differs from the frozen repository_commit_under_test"
        )
    status = _git(("status", "--porcelain", "--untracked-files=all", "--", *_PRODUCTION_PATHS)).stdout.strip()
    if status:
        raise SystemExit("B0-S0 refused to start: production source paths contain local tracked/untracked changes")


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot load retained attempt manifest {path}: {exc}") from exc
    if type(value) is not dict:
        raise SystemExit(f"attempt manifest is not an object: {path}")
    return cast(dict[str, object], value)


def _retained_manifests(results_root: Path, schedule: Mapping[str, object]) -> list[dict[str, object]]:
    manifests: list[dict[str, object]] = []
    attempts = schedule.get("attempts")
    assert type(attempts) is list
    for raw_identity in attempts:
        identity = cast(dict[str, object], raw_identity)
        directory = results_root / attempt_relative_path(cast(object, identity))
        if not directory.exists():
            continue
        manifest_path = directory / "attempt-manifest.json"
        if not manifest_path.is_file():
            raise SystemExit(
                f"incomplete retained attempt directory blocks safe resume: {directory}; do not rerun it manually"
            )
        manifest = _load_manifest(manifest_path)
        if manifest.get("identity") != identity:
            raise SystemExit(f"retained attempt identity mismatch: {manifest_path}")
        manifests.append(manifest)
    return manifests


def _assert_runner_commit_stable(manifests: Sequence[Mapping[str, object]], runner_commit: str) -> None:
    recorded: set[str] = set()
    for manifest in manifests:
        telemetry = manifest.get("telemetry")
        if type(telemetry) is dict:
            value = cast(dict[str, object], telemetry).get("runner_commit")
            if type(value) is str:
                recorded.add(value)
    if recorded and recorded != {runner_commit}:
        raise SystemExit(
            "B0-S0 refused to resume with a different runner commit after scoring started: "
            f"retained={sorted(recorded)!r}, current={runner_commit!r}"
        )


def _aggregate_metric(manifests: Sequence[Mapping[str, object]], field: str) -> dict[str, object]:
    values: list[int] = []
    for manifest in manifests:
        telemetry = manifest.get("telemetry")
        value = cast(dict[str, object], telemetry).get(field) if type(telemetry) is dict else None
        if type(value) is int:
            values.append(value)
    return {
        "available_count": len(values),
        "trial_count": len(manifests),
        "mean": None if not values else statistics.mean(values),
        "median": None if not values else statistics.median(values),
    }


def _summary(preregistration: Mapping[str, object], schedule: Mapping[str, object], manifests: Sequence[Mapping[str, object]], runner_commit: str) -> dict[str, object]:
    attempts = schedule.get("attempts")
    assert type(attempts) is list
    if len(manifests) != len(attempts):
        raise SystemExit(f"cannot summarize incomplete cohort: retained={len(manifests)}, scheduled={len(attempts)}")
    by_attempt = {
        cast(dict[str, object], manifest["identity"])["attempt_id"]: manifest
        for manifest in manifests
    }
    methods = [cast(dict[str, object], item)["id"] for item in cast(list[object], preregistration["scored_methods"])]
    method_summaries: list[dict[str, object]] = []
    for method_id in methods:
        selected: list[Mapping[str, object]] = []
        for raw_identity in attempts:
            identity = cast(dict[str, object], raw_identity)
            if identity["method_id"] == method_id:
                selected.append(by_attempt[cast(str, identity["attempt_id"])])
        completions = sum(manifest.get("completion") is True for manifest in selected)
        structural_passes = 0
        fractions: list[float] = []
        failure_counts: Counter[str] = Counter()
        for manifest in selected:
            structural = cast(dict[str, object], manifest["structural"])
            structural_passes += structural.get("all_rules_pass") is True
            denominator = cast(int, structural["fraction_denominator"])
            numerator = cast(int, structural["fraction_numerator"])
            fractions.append(numerator / denominator)
            category = manifest.get("failure_category")
            if type(category) is str:
                failure_counts[category] += 1
        method_summaries.append(
            {
                "method_id": method_id,
                "scheduled_trials": len(selected),
                "completion_rate": completions / len(selected),
                "structural_pass_rate": structural_passes / len(selected),
                "mean_structural_fraction": statistics.mean(fractions),
                "failure_counts": dict(sorted(failure_counts.items())),
                "complexity": {field: _aggregate_metric(selected, field) for field in _COMPLEXITY_FIELDS},
            }
        )
    return {
        "schema": SUMMARY_SCHEMA_V1,
        "benchmark_id": "B0",
        "freeze_commit": B0_FREEZE_COMMIT,
        "repository_commit_under_test": preregistration["repository_commit_under_test"],
        "runner_commit": runner_commit,
        "scheduled_attempt_count": len(attempts),
        "retained_attempt_count": len(manifests),
        "void_infrastructure_count": sum(manifest.get("failure_category") == "void_infrastructure" for manifest in manifests),
        "methods": method_summaries,
        "claim_boundary": "development-visible matched architecture diagnostic; no composite winner; human review pending",
    }


def _write_blind_review(results_root: Path, review_root: Path, schedule: Mapping[str, object], manifests: Sequence[Mapping[str, object]]) -> dict[str, object]:
    target_root = review_root / B0_FREEZE_COMMIT
    if target_root.exists():
        raise SystemExit(f"refusing to overwrite blind review package: {target_root}")
    target_root.mkdir(parents=True)
    by_attempt = {
        cast(dict[str, object], manifest["identity"])["attempt_id"]: manifest
        for manifest in manifests
    }
    attempts = cast(list[object], schedule["attempts"])
    entries: list[dict[str, object]] = []
    grouped: dict[str, list[dict[str, object]]] = {}
    for raw_identity in attempts:
        identity = cast(dict[str, object], raw_identity)
        manifest = by_attempt[cast(str, identity["attempt_id"])]
        if manifest.get("completion") is not True:
            continue
        key = blind_review_key(cast(object, identity))
        grouped.setdefault(cast(str, identity["task_id"]), []).append(
            {"identity": identity, "manifest": manifest, "key": key}
        )
    for task_id in sorted(grouped):
        task_dir = target_root / task_id
        task_dir.mkdir()
        ordered = sorted(grouped[task_id], key=lambda item: cast(str, item["key"]))
        for rank, item in enumerate(ordered, start=1):
            identity = cast(dict[str, object], item["identity"])
            key = cast(str, item["key"])
            source = results_root / attempt_relative_path(cast(object, identity)) / "preview-8x.png"
            if not source.is_file():
                raise SystemExit(f"completed attempt is missing preview-8x.png: {source}")
            filename = f"{rank:02d}-{key[:16]}.png"
            destination = task_dir / filename
            shutil.copyfile(source, destination)
            entries.append(
                {
                    "review_id": key,
                    "task_id": task_id,
                    "trial_index": identity["trial_index"],
                    "order": rank,
                    "preview": str(destination.relative_to(target_root)).replace("\\", "/"),
                }
            )
    manifest = {
        "schema": BLIND_REVIEW_SCHEMA_V1,
        "freeze_commit": B0_FREEZE_COMMIT,
        "ordering": "ascending sha256('<task_id>|<trial_index>|<method_id>') within task",
        "method_labels_exposed": False,
        "dimensions": ["recognizability", "readability_at_native_1x", "style_coherence"],
        "scale": "integer 1-5",
        "entries": entries,
    }
    (target_root / "manifest.json").write_bytes(json_payload(manifest))
    return manifest


def run_cohort(preregistration_path: Path, results_root: Path, review_root: Path) -> dict[str, object]:
    preregistration, preregistration_sha256 = load_b0_preregistration(preregistration_path)
    validate_b0_scoring_contract(preregistration)
    _verify_source_boundary(preregistration)
    runner_commit = _runner_commit()
    schedule = build_b0_schedule(preregistration, preregistration_sha256=preregistration_sha256)
    retained = _retained_manifests(results_root, schedule)
    _assert_runner_commit_stable(retained, runner_commit)

    attempts = cast(list[object], schedule["attempts"])
    if retained:
        retained_ids = {cast(dict[str, object], manifest["identity"])["attempt_id"] for manifest in retained}
    else:
        retained_ids = set()

    for raw_identity in attempts:
        identity = cast(dict[str, object], raw_identity)
        build_b0_provider_request(preregistration, identity=cast(object, identity))
    first_identity = cast(dict[str, object], attempts[0])
    first_request = build_b0_provider_request(preregistration, identity=cast(object, first_identity))
    executor = B0CodexExecutor()
    environment = executor.preflight(first_request)

    for raw_identity in attempts:
        identity = cast(dict[str, object], raw_identity)
        if identity["attempt_id"] in retained_ids:
            continue
        execution = run_b0_attempt(
            preregistration,
            identity=cast(object, identity),
            executor=executor,
            runner_commit=runner_commit,
        )
        write_attempt_record(results_root, preregistration, execution.result, execution.payloads)

    retained = _retained_manifests(results_root, schedule)
    summary = _summary(preregistration, schedule, retained, runner_commit)
    summary["provider_environment"] = environment
    cohort_root = results_root / B0_FREEZE_COMMIT
    cohort_root.mkdir(parents=True, exist_ok=True)
    summary_path = cohort_root / "cohort-summary.json"
    if summary_path.exists():
        raise SystemExit(f"refusing to overwrite cohort summary: {summary_path}")
    review = _write_blind_review(results_root, review_root, schedule, retained)
    summary["blind_review_entry_count"] = len(cast(list[object], review["entries"]))
    summary_path.write_bytes(json_payload(summary))
    return summary


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the frozen owner-local B0-S0 scored visible cohort.")
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    args = parser.parse_args(argv)
    summary = run_cohort(args.preregistration, args.results_root, args.review_root)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":
    main()
