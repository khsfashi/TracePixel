from __future__ import annotations

import argparse
import io
import json
from pathlib import Path, PurePosixPath
from typing import Sequence
import urllib.request
import zipfile

from evidence.g8_h4 import owner_evidence as base

FIRST_REAL_ATTEMPT_RUN_ID = 32111453098
FIRST_REAL_ATTEMPT_ARTIFACT_ID = 9315231038
RETRY_WORKFLOW_FILE = "g8-h4-preview-retry.yml"


def _seed_first_real_attempt(
    prior_root: Path,
    *,
    repository: str,
    token: str,
    current_run_id: int,
) -> None:
    if current_run_id <= FIRST_REAL_ATTEMPT_RUN_ID:
        return
    destination = prior_root / str(FIRST_REAL_ATTEMPT_RUN_ID)
    attempt = destination / "attempt-complexity.json"
    if attempt.is_file():
        return

    destination.mkdir(parents=True, exist_ok=True)
    url = (
        f"https://api.github.com/repos/{repository}/actions/artifacts/"
        f"{FIRST_REAL_ATTEMPT_ARTIFACT_ID}/zip"
    )
    request = urllib.request.Request(url, headers=base._headers(token))
    with urllib.request.urlopen(request, timeout=60) as response:
        archive_bytes = response.read()

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

    if not attempt.is_file() and not (destination / "complexity.json").is_file():
        raise RuntimeError("first real H4 attempt artifact did not contain retained complexity evidence")


def finalize(
    current: Path,
    prior_root: Path,
    *,
    repository: str,
    owner: str,
    token: str,
    current_run_id: int,
) -> dict[str, object]:
    _seed_first_real_attempt(
        prior_root,
        repository=repository,
        token=token,
        current_run_id=current_run_id,
    )

    original_workflows = base.WORKFLOW_FILES
    base.WORKFLOW_FILES = tuple(dict.fromkeys((*original_workflows, RETRY_WORKFLOW_FILE)))
    try:
        return base.finalize(
            current,
            prior_root,
            repository=repository,
            owner=owner,
            token=token,
            current_run_id=current_run_id,
        )
    finally:
        base.WORKFLOW_FILES = original_workflows


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize/verify G8-H4 retry evidence while retaining the first real failed attempt."
    )
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
        value = base.verify(args.current)
        print(
            json.dumps(
                {
                    "status": "pass",
                    "attempt_count": value["complexity"].get("attempt_count"),
                    "provider_calls": value["complexity"].get("provider_calls"),
                },
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
