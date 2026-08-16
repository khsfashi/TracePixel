from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence, cast

from evidence.p6_v3.checkpoint import build_reference_gallery


MOBILE_REVIEW_PROOF_SCHEMA_V1 = "tracepixel.mobile-review-proof.v1"
TRUSTED_REPOSITORY = "khsfashi/TracePixel"
ARTIFACT_PREFIX = "tracepixel-static-gallery-"

_REQUIRED_SECTION_IDS = (
    "final-title",
    "qa-title",
    "stages-title",
    "intent-title",
    "authority-title",
)
_REQUIRED_OBSERVATIONS = (
    "task_intent",
    "final_output",
    "stage_progression",
    "deterministic_qa",
    "agent_complexity",
)


class MobileReviewContractError(AssertionError):
    """Raised when the P6-V5 mobile review surface/proof violates its frozen contract."""


def validate_mobile_review_surface(html_bytes: bytes) -> None:
    """Require the static gallery to expose every P6-V5 review target in phone order."""

    try:
        document = html_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MobileReviewContractError("gallery HTML must be UTF-8") from exc

    viewport = 'name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"'
    if viewport not in document:
        raise MobileReviewContractError("mobile viewport contract is missing")

    positions: list[int] = []
    for section_id in _REQUIRED_SECTION_IDS:
        token = f'id="{section_id}"'
        position = document.find(token)
        if position < 0:
            raise MobileReviewContractError(f"required review section missing: {section_id}")
        positions.append(position)
    if positions != sorted(positions):
        raise MobileReviewContractError("mobile review sections are not in the frozen scan order")

    for label in ("QA", "Stages", "Complexity", "Canvas"):
        if f">{label}</span>" not in document:
            raise MobileReviewContractError(f"required summary badge missing: {label}")

    required_text = (
        "Final output",
        "Deterministic QA + Agent metrics",
        "Stage progression evidence",
        "Task / intent",
        "Authority boundary",
        "Nearest-neighbor final pixel-art preview",
        "TracePixel QA and Agent complexity composition",
        "TracePixel authored-stage contact sheet",
    )
    for token in required_text:
        if token not in document:
            raise MobileReviewContractError(f"required mobile review cue missing: {token!r}")

    lowered = document.lower()
    if "<script" in lowered or "http://" in lowered or "https://" in lowered:
        raise MobileReviewContractError("mobile review surface must remain script/network independent")


def _require_positive_int(value: object, path: str) -> int:
    if type(value) is not int or value <= 0:
        raise MobileReviewContractError(f"{path} must be a positive integer")
    return cast(int, value)


def validate_mobile_review_proof(proof: object) -> None:
    """Validate one owner-recorded phone review proof without treating aesthetics as machine truth."""

    if type(proof) is not dict:
        raise MobileReviewContractError("proof must be a JSON object")
    record = cast(dict[str, object], proof)

    if record.get("schema") != MOBILE_REVIEW_PROOF_SCHEMA_V1:
        raise MobileReviewContractError(
            f"proof.schema must be {MOBILE_REVIEW_PROOF_SCHEMA_V1!r}"
        )
    if record.get("repository") != TRUSTED_REPOSITORY:
        raise MobileReviewContractError(f"proof.repository must be {TRUSTED_REPOSITORY!r}")

    source_sha = record.get("source_sha")
    if type(source_sha) is not str or re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
        raise MobileReviewContractError("proof.source_sha must be a lowercase 40-hex commit SHA")

    _require_positive_int(record.get("workflow_run_id"), "proof.workflow_run_id")
    _require_positive_int(record.get("artifact_id"), "proof.artifact_id")

    artifact_name = record.get("artifact_name")
    expected_name = ARTIFACT_PREFIX + source_sha
    if artifact_name != expected_name:
        raise MobileReviewContractError(
            f"proof.artifact_name must match trusted source SHA: {expected_name!r}"
        )

    if record.get("device_class") != "phone":
        raise MobileReviewContractError("proof.device_class must be 'phone'")
    if record.get("access_path") != "github-actions-artifact-download":
        raise MobileReviewContractError(
            "proof.access_path must be 'github-actions-artifact-download'"
        )
    if record.get("perceptual_vlm_used") is not False:
        raise MobileReviewContractError("P6-V5 proof must not cross unresolved G4")
    if record.get("self_hosted_runner_used") is not False:
        raise MobileReviewContractError("P6-V5 proof must not cross unresolved G6")

    observations = record.get("observations")
    if type(observations) is not dict:
        raise MobileReviewContractError("proof.observations must be an object")
    typed_observations = cast(dict[str, object], observations)
    if tuple(typed_observations.keys()) != _REQUIRED_OBSERVATIONS:
        raise MobileReviewContractError(
            "proof.observations must contain the frozen P6-V5 observation keys in order"
        )
    missing = [name for name in _REQUIRED_OBSERVATIONS if typed_observations[name] is not True]
    if missing:
        raise MobileReviewContractError(
            "owner must positively identify every required mobile review target: "
            + ", ".join(missing)
        )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the P6-V5 phone review surface and, optionally, one owner-recorded "
            "mobile review proof."
        )
    )
    parser.add_argument(
        "--proof",
        type=Path,
        help="optional tracepixel.mobile-review-proof.v1 JSON record to validate",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    gallery = build_reference_gallery()
    validate_mobile_review_surface(gallery.html)

    proof_state = "manual-proof-required"
    if args.proof is not None:
        proof = json.loads(args.proof.read_text(encoding="utf-8"))
        validate_mobile_review_proof(proof)
        proof_state = "manual-proof-valid"

    print(
        "P6-V5 mobile review checkpoint passed: "
        "surface=phone-scan-order targets=5 "
        f"proof={proof_state} scripts=0 external_dependencies=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
