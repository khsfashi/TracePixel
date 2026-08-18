from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from typing import Sequence, cast
import urllib.request
import zipfile

from evidence.g8_h4.cumulative_complexity import aggregate_directories


WORKFLOW_FILES = (
    "owner-g8-h4-retained-authoring.yml",
    "owner-g8-h4-push-executor.yml",
    "owner-g8-h4-command-executor.yml",
    "owner-g8-h4-pr-executor.yml",
    "owner-g8-h4-final-executor.yml",
)

REQUIRED_RAW_FIELDS = (
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

PERCENT_COMPARISON_FIELDS = (
    "provider_calls",
    "input_tokens",
    "output_tokens",
    "iterations",
    "revisions",
    "operation_calls",
    "pixel_edits",
    "changed_pixels",
    "wall_time_ns",
)

REQUIRED_REVIEW_FILES = (
    "final.png",
    "preview-8x.png",
    "stage-index.json",
    "review-package/index.html",
    "review-package/index.ko.html",
    "review-package/H5_REVIEW.md",
)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TracePixel-G8-H4-owner-evidence",
    }


def _get_json(url: str, token: str) -> dict[str, object]:
    request = urllib.request.Request(url, headers=_headers(token))
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.load(response)
    if type(value) is not dict:
        raise ValueError(f"GitHub response for {url} must be an object")
    return cast(dict[str, object], value)


def preserve_current_attempt(current: Path) -> Path:
    current.mkdir(parents=True, exist_ok=True)
    attempt = current / "attempt-complexity.json"
    legacy = current / "complexity.json"
    if not attempt.is_file() and legacy.is_file():
        shutil.copy2(legacy, attempt)
    if not attempt.is_file():
        _write_json(
            attempt,
            {
                "measurement_scope": "single-retained-authoring-attempt",
                "raw_usage_authoritative": True,
                "price_conversion_authoritative": False,
                "provider_calls": None,
                "input_tokens": None,
                "output_tokens": None,
                "iterations": None,
                "revisions": None,
                "operation_calls": None,
                "pixel_edits": None,
                "changed_pixels": None,
                "repair_vs_regeneration": {
                    "repair_provider_calls": None,
                    "regeneration_provider_calls": None,
                    "canvas_restarts": None,
                },
                "wall_time_ns": None,
                "cache_or_profile_reuse": {
                    "humanoid_profile_reused": None,
                    "pose_profile_reused": None,
                    "profile_research_provider_calls": None,
                },
                "evidence_completeness": "incomplete-failure-before-exact-attempt-complexity",
            },
        )
    return attempt


def collect_prior_attempts(
    prior_root: Path,
    *,
    repository: str,
    owner: str,
    token: str,
    current_run_id: int,
) -> list[int]:
    prior_root.mkdir(parents=True, exist_ok=True)
    retained_run_ids: list[int] = []
    seen: set[int] = set()

    for workflow in WORKFLOW_FILES:
        url = (
            f"https://api.github.com/repos/{repository}/actions/workflows/{workflow}/runs"
            "?status=completed&per_page=100"
        )
        try:
            runs_value = _get_json(url, token).get("workflow_runs", [])
        except Exception:
            continue
        if type(runs_value) is not list:
            continue
        for run_value in cast(list[object], runs_value):
            if type(run_value) is not dict:
                continue
            run = cast(dict[str, object], run_value)
            run_id = run.get("id")
            actor = run.get("actor")
            actor_login = actor.get("login") if type(actor) is dict else None
            if type(run_id) is not int or run_id <= 0 or run_id >= current_run_id:
                continue
            if run_id in seen or actor_login != owner:
                continue
            seen.add(run_id)

            artifacts_value = _get_json(
                f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
                token,
            ).get("artifacts", [])
            if type(artifacts_value) is not list:
                continue
            retained: dict[str, object] | None = None
            for artifact_value in cast(list[object], artifacts_value):
                if type(artifact_value) is not dict:
                    continue
                artifact = cast(dict[str, object], artifact_value)
                name = artifact.get("name")
                if (
                    type(name) is str
                    and name.startswith("g8-h4-retained-authoring-")
                    and artifact.get("expired") is not True
                ):
                    retained = artifact
                    break
            if retained is None:
                continue
            archive_url = retained.get("archive_download_url")
            if type(archive_url) is not str:
                continue
            request = urllib.request.Request(archive_url, headers=_headers(token))
            with urllib.request.urlopen(request, timeout=60) as response:
                archive_bytes = response.read()

            destination = prior_root / str(run_id)
            destination.mkdir(parents=True, exist_ok=True)
            wanted = {
                "attempt-complexity.json",
                "complexity.json",
                "summary.json",
                "failure.json",
            }
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                for member in archive.namelist():
                    basename = PurePosixPath(member).name
                    if basename in wanted:
                        (destination / basename).write_bytes(archive.read(member))
            if (destination / "attempt-complexity.json").is_file() or (
                destination / "complexity.json"
            ).is_file():
                retained_run_ids.append(run_id)

    return sorted(retained_run_ids)


def finalize(
    current: Path,
    prior_root: Path,
    *,
    repository: str,
    owner: str,
    token: str,
    current_run_id: int,
) -> dict[str, object]:
    preserve_current_attempt(current)
    prior = collect_prior_attempts(
        prior_root,
        repository=repository,
        owner=owner,
        token=token,
        current_run_id=current_run_id,
    )
    cumulative = aggregate_directories(
        current,
        prior_root,
        current_run_id=current_run_id,
    )
    _write_json(current / "complexity.json", cumulative)
    _write_json(
        current / "owner-evidence-index.json",
        {
            "current_run_id": current_run_id,
            "prior_retained_attempt_run_ids": prior,
            "attempt_count": cumulative.get("attempt_count"),
            "authority": "raw-usage-metrics",
            "owner_acceptance_state": cumulative.get("owner_acceptance_state"),
        },
    )
    return cumulative


def verify(current: Path) -> dict[str, object]:
    summary = _read_json(current / "summary.json")
    complexity = _read_json(current / "complexity.json")

    if summary.get("status") != "succeeded":
        raise ValueError(f"retained authoring status is {summary.get('status')!r}, not succeeded")
    if summary.get("owner_verdict") != "pending":
        raise ValueError("H4 automation must not self-approve H5")
    if summary.get("new_schema_or_contract_added") is True:
        raise ValueError("H4 must not add a schema or contract")
    if summary.get("new_raster_authority_added") is True:
        raise ValueError("H4 must reuse the existing raster authority")
    if summary.get("animation_advanced") is True or summary.get("trace2d_integration_advanced") is True:
        raise ValueError("H4 must not advance G9 animation or Trace2D integration")

    if complexity.get("measurement_scope") != "all-retained-g8-h4-attempts-through-owner-acceptable-candidate":
        raise ValueError("H4 complexity is not cumulative through the owner candidate")
    if complexity.get("owner_acceptance_state") != "pending":
        raise ValueError("H4 cumulative evidence must remain pending until H5")
    authority = complexity.get("authority")
    if type(authority) is not dict:
        raise ValueError("H4 complexity authority is missing")
    authority_object = cast(dict[str, object], authority)
    if authority_object.get("authoritative_evidence") != "raw-usage-metrics":
        raise ValueError("raw usage metrics must remain authoritative")
    if authority_object.get("price_fields_used_for_comparison") is not False:
        raise ValueError("price conversion must not be authoritative comparison evidence")

    completeness = complexity.get("usage_completeness")
    if type(completeness) is not dict:
        raise ValueError("cumulative raw-usage completeness map is missing")
    completeness_object = cast(dict[str, object], completeness)
    incomplete = [field for field in REQUIRED_RAW_FIELDS if completeness_object.get(field) is not True]
    if incomplete:
        raise ValueError("incomplete cumulative raw usage: " + ", ".join(incomplete))

    provider_calls = complexity.get("provider_calls")
    if type(provider_calls) is not int or provider_calls < 1:
        raise ValueError("at least one real provider call is required")
    repair = complexity.get("repair_vs_regeneration")
    reuse = complexity.get("cache_or_profile_reuse")
    if type(repair) is not dict or type(reuse) is not dict:
        raise ValueError("repair/reuse cumulative evidence is missing")
    repair_object = cast(dict[str, object], repair)
    reuse_object = cast(dict[str, object], reuse)
    if repair_object.get("regeneration_provider_calls") != 0:
        raise ValueError("H4 must repair the same canvas rather than regenerate")
    if reuse_object.get("humanoid_profile_reused_for_all_provider_attempts") is not True:
        raise ValueError("not every provider attempt reused the bound humanoid profile")
    if reuse_object.get("pose_profile_reused_for_all_provider_attempts") is not True:
        raise ValueError("not every provider attempt reused the bound pose")
    if reuse_object.get("profile_research_provider_calls") != 0:
        raise ValueError("H4 must not spend provider calls on profile research")

    comparison = complexity.get("p10_c4_comparison")
    metrics = comparison.get("metrics") if type(comparison) is dict else None
    if type(metrics) is not dict:
        raise ValueError("P10-C4 comparison metrics are missing")
    metrics_object = cast(dict[str, object], metrics)
    for field in PERCENT_COMPARISON_FIELDS:
        record = metrics_object.get(field)
        if type(record) is not dict or cast(dict[str, object], record).get("percent_change") is None:
            raise ValueError(f"P10-C4 percent change is missing for {field}")

    missing = [str(path) for relative in REQUIRED_REVIEW_FILES if not (current / relative).is_file() for path in [relative]]
    if missing:
        raise ValueError("required H5 review evidence missing: " + ", ".join(missing))

    return {"summary": summary, "complexity": complexity}


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize and verify retained G8-H4 owner evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--current", type=Path, required=True)
    finalize_parser.add_argument("--prior-root", type=Path, required=True)
    finalize_parser.add_argument("--repository", required=True)
    finalize_parser.add_argument("--owner", required=True)
    finalize_parser.add_argument("--token", required=True)
    finalize_parser.add_argument("--current-run-id", type=int, required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--current", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "finalize":
        value = finalize(
            args.current,
            args.prior_root,
            repository=args.repository,
            owner=args.owner,
            token=args.token,
            current_run_id=args.current_run_id,
        )
        print(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        return 0
    if args.command == "verify":
        value = verify(args.current)
        print(json.dumps({"status": "pass", "provider_calls": value["complexity"].get("provider_calls")}, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
