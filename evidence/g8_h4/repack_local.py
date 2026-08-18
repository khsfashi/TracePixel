from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import cast

from evidence.g8_h4.cumulative_complexity import aggregate_directories
from evidence.g8_h4.owner_evidence import verify


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repack_local(
    *,
    current: Path,
    prior_root: Path,
    trigger: Path,
) -> dict[str, object]:
    trigger_value = _read_json(trigger)
    candidate_run_id = trigger_value.get("candidate_run_id")
    expected_prior = trigger_value.get("expected_prior_run_ids")
    if type(candidate_run_id) is not int or candidate_run_id <= 0:
        raise ValueError("candidate_run_id must be a positive integer")
    if type(expected_prior) is not list or any(type(value) is not int or value <= 0 for value in expected_prior):
        raise ValueError("expected_prior_run_ids must be an array of positive integers")
    prior_ids = cast(list[int], expected_prior)

    summary = _read_json(current / "summary.json")
    if summary.get("status") != "succeeded":
        raise ValueError("the retained candidate must already have succeeded")
    if summary.get("owner_verdict") != "pending":
        raise ValueError("the retained candidate must remain pending for H5")
    if not (current / "attempt-complexity.json").is_file():
        raise ValueError("candidate attempt-complexity.json is missing")

    candidate_complexity = current / "complexity.json"
    if candidate_complexity.is_file() and not (current / "candidate-run-complexity.json").is_file():
        shutil.copy2(candidate_complexity, current / "candidate-run-complexity.json")

    for run_id in prior_ids:
        directory = prior_root / str(run_id)
        if not directory.is_dir():
            raise ValueError(f"downloaded prior directory is missing for run {run_id}")
        if not (directory / "attempt-complexity.json").is_file():
            raise ValueError(f"prior run {run_id} is missing attempt-complexity.json")

    cumulative = aggregate_directories(
        current,
        prior_root,
        current_run_id=candidate_run_id,
    )
    included = cumulative.get("included_attempts")
    if type(included) is not list:
        raise ValueError("cumulative evidence is missing included_attempts")
    included_ids: set[int] = set()
    for raw in cast(list[object], included):
        if type(raw) is not dict:
            continue
        run_id = cast(dict[str, object], raw).get("run_id")
        if type(run_id) is int:
            included_ids.add(run_id)
    expected_ids = {candidate_run_id, *prior_ids}
    if included_ids != expected_ids:
        raise ValueError(
            f"included run ids {sorted(included_ids)} do not equal expected {sorted(expected_ids)}"
        )
    if cumulative.get("attempt_count") != len(expected_ids):
        raise ValueError("cumulative attempt_count does not match the retained attempts")

    _write_json(current / "complexity.json", cumulative)
    _write_json(
        current / "repack-provenance.json",
        {
            "schema": "tracepixel.g8-h4-owner-review-repack.v1",
            "candidate_run_id": candidate_run_id,
            "prior_retained_attempt_run_ids": sorted(prior_ids),
            "included_run_ids": sorted(expected_ids),
            "provider_calls_during_repack": 0,
            "raster_changes_during_repack": 0,
            "candidate_png_sha256": summary.get("final_png_sha256"),
            "raw_usage_authority": "complexity.json",
            "price_conversion_authority": "derived-non-authoritative",
            "owner_verdict": "pending",
        },
    )

    guide = current / "review-package" / "H5_REVIEW.md"
    if guide.is_file():
        with guide.open("a", encoding="utf-8") as handle:
            handle.write(
                "\n## Repacked cumulative H4 complexity\n\n"
                "This package preserves the exact succeeded candidate PNG and replaces only `complexity.json` with cumulative raw usage across the retained authoring attempts listed in `repack-provenance.json`. The repack performs zero provider calls and zero raster changes. Raw usage is authoritative; price conversion remains derived/non-authoritative.\n"
            )

    verify(current)
    return cumulative


def main() -> int:
    parser = argparse.ArgumentParser(description="Repack already-downloaded H4 artifacts into one cumulative owner-review package.")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--prior-root", type=Path, required=True)
    parser.add_argument("--trigger", type=Path, required=True)
    args = parser.parse_args()
    cumulative = repack_local(current=args.current, prior_root=args.prior_root, trigger=args.trigger)
    print(
        json.dumps(
            {
                "status": "pass",
                "attempt_count": cumulative.get("attempt_count"),
                "provider_calls": cumulative.get("provider_calls"),
                "input_tokens": cumulative.get("input_tokens"),
                "output_tokens": cumulative.get("output_tokens"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
