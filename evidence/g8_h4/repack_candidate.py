from __future__ import annotations

import argparse
import io
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import cast
import urllib.request
import zipfile

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


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TracePixel-G8-H4-candidate-repack",
    }


def _get_json(url: str, token: str) -> dict[str, object]:
    request = urllib.request.Request(url, headers=_headers(token))
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.load(response)
    if type(value) is not dict:
        raise ValueError(f"GitHub response for {url} must be an object")
    return cast(dict[str, object], value)


def _artifact_for_run(repository: str, token: str, run_id: int) -> dict[str, object]:
    payload = _get_json(
        f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
        token,
    )
    artifacts = payload.get("artifacts", [])
    if type(artifacts) is not list:
        raise ValueError(f"run {run_id} artifacts response is malformed")
    expected = f"g8-h4-retained-authoring-{run_id}"
    for raw in cast(list[object], artifacts):
        if type(raw) is not dict:
            continue
        artifact = cast(dict[str, object], raw)
        if artifact.get("name") == expected and artifact.get("expired") is not True:
            return artifact
    raise ValueError(f"run {run_id} has no retained H4 artifact named {expected!r}")


def _download_archive(artifact: dict[str, object], token: str) -> bytes:
    url = artifact.get("archive_download_url")
    if type(url) is not str:
        raise ValueError("artifact archive_download_url is missing")
    request = urllib.request.Request(url, headers=_headers(token))
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _extract_all(archive_bytes: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe artifact member path: {member.filename!r}")
            if member.is_dir():
                continue
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))


def _extract_attempt_evidence(archive_bytes: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    wanted = {"attempt-complexity.json", "complexity.json", "summary.json", "failure.json"}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for member in archive.infolist():
            basename = PurePosixPath(member.filename).name
            if basename not in wanted or member.is_dir():
                continue
            (destination / basename).write_bytes(archive.read(member))


def _artifact_fact(artifact: dict[str, object], run_id: int) -> dict[str, object]:
    return {
        "run_id": run_id,
        "artifact_id": artifact.get("id"),
        "artifact_name": artifact.get("name"),
        "artifact_digest": artifact.get("digest"),
        "expired": artifact.get("expired"),
    }


def repack(
    *,
    repository: str,
    token: str,
    trigger_path: Path,
    output: Path,
) -> dict[str, object]:
    trigger = _read_json(trigger_path)
    candidate_run_id = trigger.get("candidate_run_id")
    expected_prior = trigger.get("expected_prior_run_ids")
    if type(candidate_run_id) is not int or candidate_run_id <= 0:
        raise ValueError("trigger candidate_run_id must be a positive integer")
    if type(expected_prior) is not list or any(type(value) is not int or value <= 0 for value in expected_prior):
        raise ValueError("trigger expected_prior_run_ids must be an array of positive integers")
    prior_run_ids = cast(list[int], expected_prior)
    if any(run_id >= candidate_run_id for run_id in prior_run_ids):
        raise ValueError("every prior run id must be less than the candidate run id")
    if len(prior_run_ids) != len(set(prior_run_ids)):
        raise ValueError("expected_prior_run_ids must not contain duplicates")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    prior_root = output.parent / "g8-h4-repack-prior"
    if prior_root.exists():
        shutil.rmtree(prior_root)
    prior_root.mkdir(parents=True)

    candidate_artifact = _artifact_for_run(repository, token, candidate_run_id)
    _extract_all(_download_archive(candidate_artifact, token), output)
    summary = _read_json(output / "summary.json")
    if summary.get("status") != "succeeded":
        raise ValueError(f"candidate run {candidate_run_id} is not a succeeded retained output")
    if summary.get("owner_verdict") != "pending":
        raise ValueError("candidate must remain pending for H5 human review")

    original_complexity = output / "complexity.json"
    if original_complexity.is_file():
        shutil.copy2(original_complexity, output / "candidate-run-complexity.json")
    if not (output / "attempt-complexity.json").is_file():
        raise ValueError("candidate retained artifact is missing attempt-complexity.json")

    prior_facts: list[dict[str, object]] = []
    for run_id in prior_run_ids:
        artifact = _artifact_for_run(repository, token, run_id)
        destination = prior_root / str(run_id)
        _extract_attempt_evidence(_download_archive(artifact, token), destination)
        if not (destination / "attempt-complexity.json").is_file():
            raise ValueError(f"prior retained run {run_id} is missing attempt-complexity.json")
        prior_facts.append(_artifact_fact(artifact, run_id))

    cumulative = aggregate_directories(
        output,
        prior_root,
        current_run_id=candidate_run_id,
    )
    included = cumulative.get("included_attempts")
    if type(included) is not list:
        raise ValueError("cumulative evidence is missing included_attempts")
    included_ids = {
        record.get("run_id")
        for record in cast(list[dict[str, object]], included)
        if type(record) is dict
    }
    expected_ids = {candidate_run_id, *prior_run_ids}
    if included_ids != expected_ids:
        raise ValueError(
            f"cumulative evidence included run ids {sorted(included_ids)} but expected {sorted(expected_ids)}"
        )
    if cumulative.get("attempt_count") != len(expected_ids):
        raise ValueError("cumulative attempt_count does not match retained authoring attempts")

    _write_json(output / "complexity.json", cumulative)
    provenance = {
        "schema": "tracepixel.g8-h4-owner-review-repack.v1",
        "candidate": _artifact_fact(candidate_artifact, candidate_run_id),
        "prior_retained_attempts": prior_facts,
        "included_run_ids": sorted(expected_ids),
        "provider_calls_during_repack": 0,
        "raster_changes_during_repack": 0,
        "candidate_png_sha256": summary.get("final_png_sha256"),
        "raw_usage_authority": "complexity.json",
        "price_conversion_authority": "derived-non-authoritative",
        "owner_verdict": "pending",
    }
    _write_json(output / "repack-provenance.json", provenance)

    guide = output / "review-package" / "H5_REVIEW.md"
    if guide.is_file():
        with guide.open("a", encoding="utf-8") as handle:
            handle.write(
                "\n## Repacked cumulative H4 complexity\n\n"
                "This review package preserves the exact successful candidate PNG and replaces only the complexity record with cumulative raw usage across every retained H4 authoring attempt through this candidate. The repack itself performs zero provider calls and zero raster changes. `complexity.json` is authoritative for provider calls, input/output tokens, iterations/revisions, operation calls, pixel edits/changed pixels, repair/regeneration, profile/pose reuse, and wall time. Price conversion remains derived/non-authoritative.\n"
            )

    verify(output)
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description="Repack one succeeded H4 candidate with exact cumulative retained usage.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--trigger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    provenance = repack(
        repository=args.repository,
        token=args.token,
        trigger_path=args.trigger,
        output=args.output,
    )
    print(json.dumps(provenance, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
