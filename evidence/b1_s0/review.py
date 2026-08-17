from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Mapping, Sequence, cast

from tracepixel.benchmark.b1_harness import B1_FREEZE_COMMIT, B1_SCORED_METHOD_IDS

OWNER_REVIEW_SCHEMA_V1 = "tracepixel.b1-owner-review.v1"
OWNER_REVIEW_SUMMARY_SCHEMA_V1 = "tracepixel.b1-owner-review-summary.v1"
BLIND_REVIEW_SCHEMA_V1 = "tracepixel.b1-blind-review-package.v1"
DIMENSIONS = ("recognizability", "readability_at_native_1x", "style_coherence")
DEFAULT_REVIEW_ROOT = Path("evidence/b1/review")


class ReviewContractError(RuntimeError):
    pass


def _load_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewContractError(f"cannot load JSON object {path}: {exc}") from exc
    if type(value) is not dict:
        raise ReviewContractError(f"expected JSON object: {path}")
    return cast(dict[str, object], value)


def _canonical_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"


def _write_exclusive(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(_canonical_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ReviewContractError(f"refusing to overwrite sealed B1 owner review evidence: {path}") from exc


def _contains_method_id(value: object) -> bool:
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        return "method_id" in mapping or any(_contains_method_id(item) for item in mapping.values())
    if type(value) is list:
        return any(_contains_method_id(item) for item in cast(list[object], value))
    return False


def load_review_manifest(review_root: Path = DEFAULT_REVIEW_ROOT) -> tuple[dict[str, object], str]:
    path = review_root / B1_FREEZE_COMMIT / "manifest.json"
    data = path.read_bytes()
    manifest = cast(dict[str, object], json.loads(data))
    if (
        manifest.get("schema") != BLIND_REVIEW_SCHEMA_V1
        or manifest.get("freeze_commit") != B1_FREEZE_COMMIT
        or manifest.get("method_labels_exposed") is not False
        or manifest.get("dimensions") != list(DIMENSIONS)
    ):
        raise ReviewContractError("B1 blind review manifest identity/contract mismatch")
    entries = manifest.get("entries")
    if type(entries) is not list or len(entries) != 28 or any(type(item) is not dict for item in entries):
        raise ReviewContractError("B1 blind review manifest must contain exactly 28 entries")
    return manifest, sha256(data).hexdigest()


def _method_for_entry(entry: Mapping[str, object]) -> str:
    task_id = entry.get("task_id")
    trial_index = entry.get("trial_index")
    review_id = entry.get("review_id")
    if type(task_id) is not str or type(trial_index) is not int or type(review_id) is not str:
        raise ReviewContractError("invalid B1 blind review entry identity")
    matches = [
        method_id
        for method_id in B1_SCORED_METHOD_IDS
        if sha256(f"{task_id}|{trial_index}|{method_id}".encode("utf-8")).hexdigest() == review_id
    ]
    if len(matches) != 1:
        raise ReviewContractError(f"cannot unblind B1 review entry: {review_id}")
    return matches[0]


def validate_owner_review(
    payload: Mapping[str, object],
    review_manifest: Mapping[str, object],
    manifest_sha256: str,
) -> tuple[list[dict[str, object]], dict[str, str]]:
    if payload.get("schema") != OWNER_REVIEW_SCHEMA_V1 or payload.get("freeze_commit") != B1_FREEZE_COMMIT:
        raise ReviewContractError("B1 owner review identity mismatch")
    if payload.get("review_manifest_sha256") != manifest_sha256 or payload.get("evaluator_role") != "repository owner":
        raise ReviewContractError("B1 owner review evaluator/manifest binding mismatch")
    if payload.get("dimensions") != list(DIMENSIONS) or _contains_method_id(payload):
        raise ReviewContractError("B1 owner review rating contract or blindness mismatch")

    raw_ratings = payload.get("ratings")
    raw_entries = review_manifest.get("entries")
    if type(raw_ratings) is not list or type(raw_entries) is not list or len(raw_ratings) != len(raw_entries):
        raise ReviewContractError("B1 owner review must rate every blind entry exactly once")

    ratings: list[dict[str, object]] = []
    mapping: dict[str, str] = {}
    for raw_rating, raw_entry in zip(raw_ratings, raw_entries, strict=True):
        if type(raw_rating) is not dict or type(raw_entry) is not dict:
            raise ReviewContractError("B1 owner review contains invalid rating object")
        rating = cast(dict[str, object], raw_rating)
        entry = cast(dict[str, object], raw_entry)
        for field in ("review_id", "task_id", "trial_index", "order"):
            if rating.get(field) != entry.get(field):
                raise ReviewContractError(f"B1 owner review order/identity mismatch: {field}")
        for dimension in DIMENSIONS:
            score = rating.get(dimension)
            if type(score) is not int or not 1 <= score <= 5:
                raise ReviewContractError(f"{dimension} must be an integer 1-5")
        if type(rating.get("human_rejection")) is not bool:
            raise ReviewContractError("human_rejection must be an explicit boolean")
        review_id = cast(str, rating["review_id"])
        mapping[review_id] = _method_for_entry(entry)
        ratings.append(rating)

    if len(mapping) != len(ratings):
        raise ReviewContractError("duplicate B1 owner review identity")
    return ratings, mapping


def owner_review_summary(
    ratings: Sequence[Mapping[str, object]],
    method_by_review_id: Mapping[str, str],
) -> dict[str, object]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for rating in ratings:
        review_id = cast(str, rating["review_id"])
        method_id = method_by_review_id.get(review_id)
        if method_id is None:
            raise ReviewContractError(f"cannot unblind unknown review_id: {review_id}")
        grouped.setdefault(method_id, []).append(rating)

    methods: list[dict[str, object]] = []
    for method_id in sorted(grouped):
        selected = grouped[method_id]
        methods.append(
            {
                "method_id": method_id,
                "rated_artifacts": len(selected),
                "human_rejection_count": sum(item.get("human_rejection") is True for item in selected),
                "mean": {
                    dimension: sum(cast(int, item[dimension]) for item in selected) / len(selected)
                    for dimension in DIMENSIONS
                },
            }
        )
    return {
        "schema": OWNER_REVIEW_SUMMARY_SCHEMA_V1,
        "freeze_commit": B1_FREEZE_COMMIT,
        "rating_count": len(ratings),
        "methods": methods,
        "claim_boundary": "human perception only; deterministic correctness remains separate; no composite winner",
    }


def seal_owner_review(
    owner_review_path: Path,
    review_root: Path = DEFAULT_REVIEW_ROOT,
) -> tuple[Path, Path]:
    payload = _load_object(owner_review_path)
    manifest, manifest_sha = load_review_manifest(review_root)
    ratings, mapping = validate_owner_review(payload, manifest, manifest_sha)
    summary = owner_review_summary(ratings, mapping)

    target = review_root / B1_FREEZE_COMMIT
    owner_target = target / "owner-review.json"
    summary_target = target / "owner-review-summary.json"
    _write_exclusive(owner_target, payload)
    _write_exclusive(summary_target, summary)
    return owner_target, summary_target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and seal the frozen B1 repository-owner blind review.")
    parser.add_argument("owner_review", type=Path)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    args = parser.parse_args(argv)
    owner, summary = seal_owner_review(args.owner_review, args.review_root)
    print(json.dumps({"owner_review": str(owner), "summary": str(summary)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
