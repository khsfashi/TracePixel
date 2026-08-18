from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence, cast

P10_C4_BASELINE = {
    "run_id": 32099831527,
    "artifact_id": 9311214420,
    "canvas": {"width": 32, "height": 32},
    "provider_calls": 1,
    "input_tokens": 18854,
    "output_tokens": 3762,
    "iterations": 1,
    "revisions": 1,
    "operation_calls": 1,
    "pixel_edits": 270,
    "changed_pixels": 270,
    "repair_provider_calls": 0,
    "regeneration_provider_calls": 0,
    "canvas_restarts": 0,
    "profile_research_provider_calls": 0,
    "profile_reused": True,
    "pose_reused": True,
    "wall_time_ns": 107656174400,
}

_NUMERIC_FIELDS = (
    "provider_calls",
    "input_tokens",
    "output_tokens",
    "iterations",
    "revisions",
    "operation_calls",
    "pixel_edits",
    "changed_pixels",
    "repair_provider_calls",
    "regeneration_provider_calls",
    "canvas_restarts",
    "profile_research_provider_calls",
    "wall_time_ns",
)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _nested_metric(complexity: dict[str, object], field: str) -> object:
    if field in complexity:
        return complexity.get(field)
    if field in ("repair_provider_calls", "regeneration_provider_calls", "canvas_restarts"):
        repair = complexity.get("repair_vs_regeneration")
        if type(repair) is dict:
            return cast(dict[str, object], repair).get(field)
    if field == "profile_research_provider_calls":
        reuse = complexity.get("cache_or_profile_reuse")
        if type(reuse) is dict:
            return cast(dict[str, object], reuse).get(field)
    return None


def _provider_reuse_state(complexity: dict[str, object], key: str) -> bool | None:
    reuse = complexity.get("cache_or_profile_reuse")
    if type(reuse) is not dict:
        return None
    value = cast(dict[str, object], reuse).get(key)
    return value if type(value) is bool else None


def _normalise_zero_call_unknowns(complexity: dict[str, object]) -> dict[str, object]:
    result = dict(complexity)
    provider_calls = _nested_metric(result, "provider_calls")
    if provider_calls == 0:
        for field in (
            "input_tokens",
            "output_tokens",
            "iterations",
            "revisions",
            "operation_calls",
            "pixel_edits",
            "changed_pixels",
            "repair_provider_calls",
            "regeneration_provider_calls",
            "canvas_restarts",
            "profile_research_provider_calls",
        ):
            if _nested_metric(result, field) is None:
                result[field] = 0
    return result


def load_attempt(directory: Path, *, run_id: int | None = None) -> dict[str, object]:
    attempt_path = directory / "attempt-complexity.json"
    legacy_path = directory / "complexity.json"
    if attempt_path.is_file():
        complexity = _json(attempt_path)
    elif legacy_path.is_file():
        complexity = _json(legacy_path)
    else:
        raise ValueError(f"no attempt complexity evidence in {directory}")
    complexity = _normalise_zero_call_unknowns(complexity)
    summary = _json(directory / "summary.json") if (directory / "summary.json").is_file() else {}
    return {
        "run_id": run_id,
        "source_sha": summary.get("source_sha"),
        "status": summary.get("status"),
        "owner_verdict": summary.get("owner_verdict"),
        "complexity": complexity,
    }


def _sum_exact(attempts: Sequence[dict[str, object]], field: str) -> tuple[int | None, int, bool]:
    total = 0
    complete = True
    for attempt in attempts:
        complexity = attempt.get("complexity")
        if type(complexity) is not dict:
            complete = False
            continue
        value = _nested_metric(cast(dict[str, object], complexity), field)
        if type(value) is int:
            total += value
        else:
            complete = False
    return (total if complete else None, total, complete)


def _rate(value: int | None, baseline: int) -> dict[str, object]:
    if value is None:
        return {
            "absolute_delta": None,
            "multiplier": None,
            "percent_change": None,
            "rate_status": "incomplete-current-raw-metric",
        }
    delta = value - baseline
    if baseline == 0:
        return {
            "absolute_delta": delta,
            "multiplier": None,
            "percent_change": None,
            "rate_status": "undefined-zero-baseline",
        }
    return {
        "absolute_delta": delta,
        "multiplier": round(value / baseline, 4),
        "percent_change": round((delta / baseline) * 100.0, 2),
        "rate_status": "defined",
    }


def build_cumulative_complexity(
    attempts: Sequence[dict[str, object]],
    *,
    candidate_run_id: int | None,
    accepted_run_id: int | None = None,
) -> dict[str, object]:
    if not attempts:
        raise ValueError("at least one retained H4 attempt is required")

    totals: dict[str, int | None] = {}
    known_totals: dict[str, int] = {}
    completeness: dict[str, bool] = {}
    for field in _NUMERIC_FIELDS:
        exact, known, complete = _sum_exact(attempts, field)
        totals[field] = exact
        known_totals[field] = known
        completeness[field] = complete

    provider_attempts = [
        attempt
        for attempt in attempts
        if type(attempt.get("complexity")) is dict
        and isinstance(_nested_metric(cast(dict[str, object], attempt["complexity"]), "provider_calls"), int)
        and cast(int, _nested_metric(cast(dict[str, object], attempt["complexity"]), "provider_calls")) > 0
    ]
    profile_states = [
        _provider_reuse_state(cast(dict[str, object], attempt["complexity"]), "humanoid_profile_reused")
        for attempt in provider_attempts
    ]
    pose_states = [
        _provider_reuse_state(cast(dict[str, object], attempt["complexity"]), "pose_profile_reused")
        for attempt in provider_attempts
    ]
    profile_reused = all(value is True for value in profile_states) if provider_attempts else True
    pose_reused = all(value is True for value in pose_states) if provider_attempts else True
    profile_reuse_complete = all(value is not None for value in profile_states)
    pose_reuse_complete = all(value is not None for value in pose_states)

    comparison_metrics: dict[str, object] = {}
    for field in _NUMERIC_FIELDS:
        baseline = cast(int, P10_C4_BASELINE[field])
        value = totals[field]
        comparison_metrics[field] = {
            "p10_c4": baseline,
            "g8_h4_cumulative": value,
            **_rate(value, baseline),
        }

    comparison = {
        "baseline": "P10-C4 owner-accepted retained simple-creature run 32099831527 / artifact 9311214420",
        "baseline_facts": P10_C4_BASELINE,
        "metrics": comparison_metrics,
        "profile_reuse": {
            "p10_c4_profile_reused": True,
            "p10_c4_pose_reused": True,
            "g8_h4_all_provider_attempts_profile_reused": profile_reused,
            "g8_h4_all_provider_attempts_pose_reused": pose_reused,
            "profile_reuse_complete": profile_reuse_complete,
            "pose_reuse_complete": pose_reuse_complete,
            "percent_change": None,
            "note": "profile reuse is boolean evidence; percentage change is not mathematically meaningful",
        },
    }

    included_attempts = [
        {
            "run_id": attempt.get("run_id"),
            "source_sha": attempt.get("source_sha"),
            "status": attempt.get("status"),
            "owner_verdict": attempt.get("owner_verdict"),
        }
        for attempt in attempts
    ]

    result: dict[str, object] = {
        "measurement_scope": "all-retained-g8-h4-attempts-through-owner-acceptable-candidate",
        "owner_acceptance_state": "frozen" if accepted_run_id is not None else "pending",
        "candidate_run_id": candidate_run_id,
        "accepted_run_id": accepted_run_id,
        "attempt_count": len(attempts),
        "provider_attempt_count": len(provider_attempts),
        "included_attempts": included_attempts,
        "authority": {
            "authoritative_evidence": "raw-usage-metrics",
            "price_conversion": "derived-non-authoritative",
            "price_fields_used_for_comparison": False,
            "final_owner_acceptable_evidence_requires_complete_raw_usage": True,
        },
        "usage_completeness": completeness,
        "known_partial_totals_when_incomplete": known_totals,
        "provider_calls": totals["provider_calls"],
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "iterations": totals["iterations"],
        "revisions": totals["revisions"],
        "operation_calls": totals["operation_calls"],
        "pixel_edits": totals["pixel_edits"],
        "changed_pixels": totals["changed_pixels"],
        "repair_vs_regeneration": {
            "repair_provider_calls": totals["repair_provider_calls"],
            "regeneration_provider_calls": totals["regeneration_provider_calls"],
            "canvas_restarts": totals["canvas_restarts"],
        },
        "wall_time_ns": totals["wall_time_ns"],
        "cache_or_profile_reuse": {
            "humanoid_profile_reused_for_all_provider_attempts": profile_reused,
            "pose_profile_reused_for_all_provider_attempts": pose_reused,
            "profile_reuse_complete": profile_reuse_complete,
            "pose_reuse_complete": pose_reuse_complete,
            "profile_research_provider_calls": totals["profile_research_provider_calls"],
        },
        "p10_c4_comparison": comparison,
    }
    return result


def aggregate_directories(
    current: Path,
    prior_root: Path | None,
    *,
    current_run_id: int | None,
    accepted_run_id: int | None = None,
) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    if prior_root is not None and prior_root.is_dir():
        prior_entries: list[tuple[int, Path]] = []
        for child in prior_root.iterdir():
            if not child.is_dir() or not child.name.isdigit():
                continue
            prior_entries.append((int(child.name), child))
        for run_id, directory in sorted(prior_entries):
            if current_run_id is not None and run_id >= current_run_id:
                continue
            attempts.append(load_attempt(directory, run_id=run_id))
    attempts.append(load_attempt(current, run_id=current_run_id))
    return build_cumulative_complexity(
        attempts,
        candidate_run_id=current_run_id,
        accepted_run_id=accepted_run_id,
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate retained G8-H4 raw complexity through a candidate/accepted output.")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--prior-root", type=Path)
    parser.add_argument("--current-run-id", type=int)
    parser.add_argument("--accepted-run-id", type=int)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    cumulative = aggregate_directories(
        args.current,
        args.prior_root,
        current_run_id=args.current_run_id,
        accepted_run_id=args.accepted_run_id,
    )
    _write_json(args.output, cumulative)
    print(json.dumps(cumulative, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
