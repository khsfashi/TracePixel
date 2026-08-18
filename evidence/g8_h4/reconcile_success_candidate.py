from __future__ import annotations

import argparse
import io
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Sequence, cast
import urllib.request
import zipfile

from evidence.g8_h4.cumulative_complexity import aggregate_directories
from evidence.g8_h4.owner_evidence import verify

FAILED_RUN_ID = 32111453098
FAILED_ARTIFACT_ID = 9315231038
FAILED_ARTIFACT_DIGEST = "sha256:58cd515072dd6ee65c062cd49f1c31ba359905b5b759b25a9fd09e7bd4b6b369"

CANDIDATE_RUN_ID = 32111680356
CANDIDATE_ARTIFACT_ID = 9315292791
CANDIDATE_ARTIFACT_DIGEST = "sha256:4afeab835c2567a4a5f5669d2a512f5260610acb7dce5802eec47d39d2ba3721"

EXPECTED_CUMULATIVE = {
    "attempt_count": 2,
    "provider_calls": 5,
    "input_tokens": 91917,
    "output_tokens": 19060,
    "iterations": 5,
    "revisions": 5,
    "operation_calls": 5,
    "pixel_edits": 1450,
    "changed_pixels": 1450,
    "repair_provider_calls": 3,
    "regeneration_provider_calls": 0,
    "canvas_restarts": 0,
    "profile_research_provider_calls": 0,
    "wall_time_ns": 517791799200,
}


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TracePixel-G8-H4-candidate-reconciliation",
    }


def _download_artifact(repository: str, artifact_id: int, token: str, destination: Path) -> None:
    url = f"https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}/zip"
    request = urllib.request.Request(url, headers=_headers(token))
    with urllib.request.urlopen(request, timeout=60) as response:
        archive_bytes = response.read()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for member in archive.namelist():
            relative = PurePosixPath(member)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe artifact member: {member}")
            target = destination.joinpath(*relative.parts)
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metric(cumulative: dict[str, object], field: str) -> object:
    if field in cumulative:
        return cumulative[field]
    if field in ("repair_provider_calls", "regeneration_provider_calls", "canvas_restarts"):
        repair = cumulative.get("repair_vs_regeneration")
        if type(repair) is dict:
            return cast(dict[str, object], repair).get(field)
    if field == "profile_research_provider_calls":
        reuse = cumulative.get("cache_or_profile_reuse")
        if type(reuse) is dict:
            return cast(dict[str, object], reuse).get(field)
    return None


def reconcile_downloaded_directories(
    candidate_source: Path,
    failed_source: Path,
    output: Path,
) -> dict[str, object]:
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(candidate_source, output)

    prior_root = output.parent / "prior-attempts"
    if prior_root.exists():
        shutil.rmtree(prior_root)
    prior = prior_root / str(FAILED_RUN_ID)
    prior.mkdir(parents=True, exist_ok=True)
    for name in ("attempt-complexity.json", "complexity.json", "summary.json", "failure.json"):
        source = failed_source / name
        if source.is_file():
            shutil.copy2(source, prior / name)

    if not (prior / "attempt-complexity.json").is_file():
        raise ValueError("first real failed attempt is missing attempt-complexity.json")
    if not (output / "attempt-complexity.json").is_file():
        raise ValueError("successful candidate is missing attempt-complexity.json")

    cumulative = aggregate_directories(
        output,
        prior_root,
        current_run_id=CANDIDATE_RUN_ID,
    )
    _write_json(output / "complexity.json", cumulative)

    included = cumulative.get("included_attempts")
    included_ids = [item.get("run_id") for item in included if type(item) is dict] if type(included) is list else []
    if included_ids != [FAILED_RUN_ID, CANDIDATE_RUN_ID]:
        raise ValueError(f"unexpected retained attempt sequence: {included_ids!r}")

    for field, expected in EXPECTED_CUMULATIVE.items():
        actual = cumulative.get("attempt_count") if field == "attempt_count" else _metric(cumulative, field)
        if actual != expected:
            raise ValueError(f"cumulative {field} mismatch: expected {expected}, got {actual}")

    verified = verify(output)
    if verified["summary"].get("source_sha") != "accb144a52b5acafcf2fbe6be3d2c3acfdeda095":
        raise ValueError("successful candidate source SHA drifted during reconciliation")

    reconciliation = {
        "schema": "tracepixel.g8-h4-candidate-reconciliation.v1",
        "candidate": {
            "run_id": CANDIDATE_RUN_ID,
            "artifact_id": CANDIDATE_ARTIFACT_ID,
            "artifact_digest": CANDIDATE_ARTIFACT_DIGEST,
            "status": "succeeded",
            "owner_verdict": "pending",
        },
        "prior_retained_attempts": [
            {
                "run_id": FAILED_RUN_ID,
                "artifact_id": FAILED_ARTIFACT_ID,
                "artifact_digest": FAILED_ARTIFACT_DIGEST,
                "status": "failed",
            }
        ],
        "provider_calls_added_by_reconciliation": 0,
        "raster_edits_added_by_reconciliation": 0,
        "authoritative_evidence": "raw-usage-metrics",
        "price_conversion": "derived-non-authoritative",
        "complexity": "complexity.json",
        "h5_owner_acceptance_state": "pending",
    }
    _write_json(output / "reconciliation.json", reconciliation)
    return {"complexity": cumulative, "reconciliation": reconciliation}


def reconcile(
    output: Path,
    work_root: Path,
    *,
    repository: str,
    token: str,
) -> dict[str, object]:
    if work_root.exists():
        shutil.rmtree(work_root)
    candidate_source = work_root / "candidate"
    failed_source = work_root / "failed"
    _download_artifact(repository, CANDIDATE_ARTIFACT_ID, token, candidate_source)
    _download_artifact(repository, FAILED_ARTIFACT_ID, token, failed_source)
    return reconcile_downloaded_directories(candidate_source, failed_source, output)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile the successful G8-H4 candidate with all retained real attempts without provider work."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    value = reconcile(
        args.output,
        args.work_root,
        repository=args.repository,
        token=args.token,
    )
    complexity = value["complexity"]
    print(
        json.dumps(
            {
                "status": "pass",
                "candidate_run_id": CANDIDATE_RUN_ID,
                "attempt_count": complexity.get("attempt_count"),
                "provider_calls": complexity.get("provider_calls"),
                "input_tokens": complexity.get("input_tokens"),
                "output_tokens": complexity.get("output_tokens"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
