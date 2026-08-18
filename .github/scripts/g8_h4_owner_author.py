from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile


ROOT = Path.cwd()
DEFAULT_OUTPUT = ROOT / "artifacts" / "g8-h4-retained"
PRIOR_ROOT = ROOT / "artifacts" / "g8-h4-prior-attempts"
WORKFLOW_FILE = "owner-g8-h4-pr-executor.yml"

NUMERIC_FIELDS = (
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
NONZERO_BASELINE_FIELDS = (
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


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def run(command: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if capture and result.stdout:
        print(result.stdout, end="")
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed with exit {result.returncode}: {' '.join(command)}")
    return result


def ensure_failure_evidence(
    output: Path,
    *,
    source_sha: str,
    message: str,
    provider_may_have_run: bool,
    started_ns: int,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    failure_path = output / "failure.json"
    if not failure_path.exists():
        write_json(
            failure_path,
            {
                "phase": "G8",
                "child": "G8-H4",
                "status": "failed-in-owner-executor",
                "source_sha": source_sha.lower(),
                "failure_type": "OwnerExecutorFailure",
                "message": message,
                "contract_first": True,
                "minimal_fix_required_before_new_schema": True,
                "new_schema_or_contract_added": False,
                "new_raster_authority_added": False,
            },
        )

    summary_path = output / "summary.json"
    if not summary_path.exists():
        write_json(
            summary_path,
            {
                "phase": "G8",
                "child": "G8-H4",
                "source_issue": 119,
                "source_sha": source_sha.lower(),
                "status": "failed",
                "owner_verdict": "pending",
                "failure_evidence": "failure.json",
                "new_schema_or_contract_added": False,
                "new_raster_authority_added": False,
                "animation_advanced": False,
                "trace2d_integration_advanced": False,
            },
        )

    attempt_path = output / "attempt-complexity.json"
    if attempt_path.exists():
        return

    elapsed_ns = max(0, time.perf_counter_ns() - started_ns)
    if provider_may_have_run:
        unknown: int | None = None
        reuse: bool | None = None
        completeness = "incomplete-failure-after-provider-command-started"
    else:
        unknown = 0
        reuse = True
        completeness = "exact-zero-provider-pre-authoring-failure"

    write_json(
        attempt_path,
        {
            "measurement_scope": "single-retained-authoring-attempt",
            "raw_usage_authoritative": True,
            "price_conversion_authoritative": False,
            "provider_calls": unknown,
            "input_tokens": unknown,
            "output_tokens": unknown,
            "iterations": unknown,
            "revisions": unknown,
            "operation_calls": unknown,
            "pixel_edits": unknown,
            "changed_pixels": unknown,
            "repair_vs_regeneration": {
                "repair_provider_calls": unknown,
                "regeneration_provider_calls": unknown,
                "canvas_restarts": unknown,
            },
            "wall_time_ns": elapsed_ns,
            "cache_or_profile_reuse": {
                "humanoid_profile_reused": reuse,
                "pose_profile_reused": reuse,
                "profile_research_provider_calls": unknown,
            },
            "evidence_completeness": completeness,
        },
    )


def github_json(url: str, *, token: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "TracePixel-G8-H4-scripted-owner-authoring",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise RuntimeError(f"GitHub response at {url} is not an object")
    return value


def collect_prior_attempts(*, repo: str, token: str, current_run_id: int) -> None:
    PRIOR_ROOT.mkdir(parents=True, exist_ok=True)
    payload = github_json(
        f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs?status=completed&per_page=100",
        token=token,
    )
    runs = payload.get("workflow_runs", [])
    if not isinstance(runs, list):
        raise RuntimeError("workflow_runs response is not a list")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TracePixel-G8-H4-scripted-owner-authoring",
    }
    for raw_run in runs:
        if not isinstance(raw_run, dict):
            continue
        run_id = raw_run.get("id")
        if not isinstance(run_id, int) or run_id <= 0 or run_id >= current_run_id:
            continue
        artifacts_payload = github_json(
            f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100",
            token=token,
        )
        artifacts = artifacts_payload.get("artifacts", [])
        if not isinstance(artifacts, list):
            continue
        retained: dict[str, object] | None = None
        expected_name = f"g8-h4-retained-authoring-{run_id}"
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            if artifact.get("expired") is False and artifact.get("name") == expected_name:
                retained = artifact
                break
        if retained is None:
            continue
        download_url = retained.get("archive_download_url")
        if not isinstance(download_url, str):
            continue
        request = urllib.request.Request(download_url, headers=headers)
        with urllib.request.urlopen(request, timeout=60) as response:
            archive_bytes = response.read()
        target = PRIOR_ROOT / str(run_id)
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = set(archive.namelist())
            for name in ("attempt-complexity.json", "complexity.json", "summary.json", "failure.json"):
                if name in names:
                    (target / name).write_bytes(archive.read(name))


def verify_candidate(output: Path) -> None:
    summary = read_json(output / "summary.json")
    complexity = read_json(output / "complexity.json")

    if summary.get("status") != "succeeded":
        raise RuntimeError(f"retained authoring did not succeed: {summary.get('failure_reasons')}")
    if summary.get("owner_verdict") != "pending":
        raise RuntimeError("H4 must not self-approve H5")
    for field in ("new_schema_or_contract_added", "new_raster_authority_added", "animation_advanced", "trace2d_integration_advanced"):
        if summary.get(field) is not False:
            raise RuntimeError(f"H4 authority boundary drifted at {field}")

    if complexity.get("measurement_scope") != "all-retained-g8-h4-attempts-through-owner-acceptable-candidate":
        raise RuntimeError("H4 cumulative measurement scope drifted")
    if complexity.get("owner_acceptance_state") != "pending":
        raise RuntimeError("H4 must not freeze owner acceptance")
    authority = complexity.get("authority")
    if not isinstance(authority, dict):
        raise RuntimeError("H4 cumulative authority block is missing")
    if authority.get("authoritative_evidence") != "raw-usage-metrics":
        raise RuntimeError("raw usage metrics must remain authoritative")
    if authority.get("price_fields_used_for_comparison") is not False:
        raise RuntimeError("price conversion must remain non-authoritative")

    completeness = complexity.get("usage_completeness")
    if not isinstance(completeness, dict):
        raise RuntimeError("cumulative raw usage completeness block is missing")
    for field in NUMERIC_FIELDS:
        if completeness.get(field) is not True:
            raise RuntimeError(f"cumulative raw metric is incomplete: {field}")

    provider_calls = complexity.get("provider_calls")
    if not isinstance(provider_calls, int) or provider_calls < 1:
        raise RuntimeError("no real provider call was retained")
    if not isinstance(complexity.get("input_tokens"), int) or not isinstance(complexity.get("output_tokens"), int):
        raise RuntimeError("exact cumulative provider token totals are required")

    repair = complexity.get("repair_vs_regeneration")
    reuse = complexity.get("cache_or_profile_reuse")
    if not isinstance(repair, dict) or repair.get("regeneration_provider_calls") != 0:
        raise RuntimeError("H4 may repair the same canvas but may not regenerate it")
    if not isinstance(reuse, dict):
        raise RuntimeError("profile/pose reuse evidence is missing")
    if reuse.get("humanoid_profile_reused_for_all_provider_attempts") is not True:
        raise RuntimeError("not all provider attempts reused the retained humanoid profile")
    if reuse.get("pose_profile_reused_for_all_provider_attempts") is not True:
        raise RuntimeError("not all provider attempts reused the retained pose")
    if reuse.get("profile_research_provider_calls") != 0:
        raise RuntimeError("H4 unexpectedly spent provider calls on profile research")

    comparison = complexity.get("p10_c4_comparison")
    metrics = comparison.get("metrics") if isinstance(comparison, dict) else None
    if not isinstance(metrics, dict):
        raise RuntimeError("P10-C4 comparison metrics are missing")
    for field in NONZERO_BASELINE_FIELDS:
        record = metrics.get(field)
        if not isinstance(record, dict) or not isinstance(record.get("percent_change"), (int, float)):
            raise RuntimeError(f"P10-C4 percentage change is missing for {field}")

    for relative in (
        "final.png",
        "preview-8x.png",
        "stage-index.json",
        "review-package/index.html",
        "review-package/index.ko.html",
        "review-package/H5_REVIEW.md",
    ):
        if not (output / relative).is_file():
            raise RuntimeError(f"required retained review evidence is missing: {relative}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output
    source_sha = args.source_sha
    started_ns = time.perf_counter_ns()
    provider_started = False
    output.mkdir(parents=True, exist_ok=True)
    PRIOR_ROOT.mkdir(parents=True, exist_ok=True)

    try:
        run(["codex", "--version"])
        login = run(["codex", "login", "status"], capture=True)
        status_text = login.stdout or ""
        if "Logged in using ChatGPT" not in status_text:
            raise RuntimeError("G8-H4 requires Codex CLI authenticated through the existing ChatGPT plan boundary")
        if "Logged in using an API key" in status_text:
            raise RuntimeError("API-key billed Codex execution is not authorized for G8-H4")

        provider_started = True
        authoring = run(
            [
                sys.executable,
                "-m",
                "evidence.g8_h4.retained_authoring",
                "--output",
                str(output),
                "--source-sha",
                source_sha,
            ],
            check=False,
        )

        legacy = output / "complexity.json"
        attempt = output / "attempt-complexity.json"
        if legacy.is_file() and not attempt.exists():
            shutil.copyfile(legacy, attempt)
        if not attempt.exists():
            ensure_failure_evidence(
                output,
                source_sha=source_sha,
                message=f"retained authoring exited without exact attempt complexity (exit {authoring.returncode})",
                provider_may_have_run=True,
                started_ns=started_ns,
            )

        import os

        repo = os.environ.get("REPOSITORY")
        token = os.environ.get("GH_TOKEN")
        run_id_raw = os.environ.get("GITHUB_RUN_ID")
        if not repo or not token or not run_id_raw:
            raise RuntimeError("REPOSITORY, GH_TOKEN, and GITHUB_RUN_ID are required for cumulative H4 evidence")
        current_run_id = int(run_id_raw)
        collect_prior_attempts(repo=repo, token=token, current_run_id=current_run_id)

        run(
            [
                sys.executable,
                "-m",
                "evidence.g8_h4.cumulative_complexity",
                "--current",
                str(output),
                "--prior-root",
                str(PRIOR_ROOT),
                "--current-run-id",
                str(current_run_id),
                "--output",
                str(output / "complexity.json"),
            ]
        )

        review_guide = output / "review-package" / "H5_REVIEW.md"
        if review_guide.is_file():
            with review_guide.open("a", encoding="utf-8") as handle:
                handle.write(
                    "\n## Cumulative complexity authority\n\n"
                    "The sibling `complexity.json` is cumulative through this candidate. Raw provider/token/edit/repair/reuse/wall-time metrics are authoritative; price conversion is derived and non-authoritative. If the owner accepts this image, H5 must freeze this exact cumulative record.\n"
                )

        if authoring.returncode != 0:
            raise RuntimeError(
                f"G8-H4 retained authoring exited with code {authoring.returncode}; retained failure evidence was preserved"
            )

        verify_candidate(output)
        print("G8-H4 retained static humanoid candidate and cumulative raw evidence verified.")
        return 0
    except BaseException as exc:
        message = str(exc)
        print(f"G8-H4 owner executor failed: {message}", file=sys.stderr)
        ensure_failure_evidence(
            output,
            source_sha=source_sha,
            message=message,
            provider_may_have_run=provider_started,
            started_ns=started_ns,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
