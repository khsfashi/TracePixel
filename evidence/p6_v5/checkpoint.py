from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Sequence, cast

from evidence.p6_v3.checkpoint import build_reference_gallery
from tracepixel.preview.mobile_review import (
    MobileReviewPackage,
    build_mobile_review_package,
    write_mobile_review_package,
)


MOBILE_REVIEW_PROOF_SCHEMA_V2 = "tracepixel.mobile-review-proof.v2"
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
_LANGUAGE_PAGE = {"en": "index.html", "ko": "index.ko.html"}


class MobileReviewContractError(AssertionError):
    """Raised when the P6-V5 mobile review surface/proof violates its frozen contract."""


def validate_mobile_review_surface(
    html_bytes: bytes,
    *,
    language: str,
    expected_stage_linkage: str,
) -> None:
    """Require one localized static page to expose every P6-V5 phone review target."""

    if language not in _LANGUAGE_PAGE:
        raise MobileReviewContractError(f"unsupported review language: {language!r}")
    if expected_stage_linkage not in ("separate-reference", "bundle-stage-artifacts"):
        raise MobileReviewContractError(f"unsupported stage linkage: {expected_stage_linkage!r}")

    try:
        document = html_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MobileReviewContractError("gallery HTML must be UTF-8") from exc

    expected_lang = f'<html lang="{language}">'
    if expected_lang not in document:
        raise MobileReviewContractError(f"localized html lang missing: {expected_lang}")

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

    if language == "en":
        badges = ("QA", "Stages", "Complexity", "Canvas")
        required_text = (
            "Final output",
            "Deterministic QA + Agent metrics",
            "Task / intent",
            "Authority boundary",
            "Nearest-neighbor final pixel-art preview",
            "TracePixel QA and Agent complexity composition",
            "TracePixel authored-stage contact sheet",
        )
        switch_target = 'href="index.ko.html"'
        linkage_cue = (
            "Reference stages — not provenance of this final output"
            if expected_stage_linkage == "separate-reference"
            else "Linked stages — exact bundle provenance"
        )
    else:
        badges = ("QA", "단계", "복잡도", "캔버스")
        required_text = (
            "최종 결과",
            "결정론적 QA + Agent 지표",
            "작업 / 의도",
            "근거 권한 경계",
            "최근접 이웃 방식으로 확대한 최종 픽셀 아트 미리보기",
            "TracePixel QA 및 Agent 복잡도 구성",
            "TracePixel 작성 단계 contact sheet",
        )
        switch_target = 'href="index.html"'
        linkage_cue = (
            "참고 단계 — 이 최종 결과의 실제 생성 이력이 아닙니다"
            if expected_stage_linkage == "separate-reference"
            else "연결된 단계 — 정확한 bundle 생성 이력"
        )

    for label in badges:
        if f">{label}</span>" not in document:
            raise MobileReviewContractError(f"required summary badge missing: {label}")
    for token in required_text:
        if token not in document:
            raise MobileReviewContractError(f"required mobile review cue missing: {token!r}")
    if switch_target not in document:
        raise MobileReviewContractError("static companion-language navigation is missing")

    linkage_token = f'data-stage-linkage="{expected_stage_linkage}"'
    if linkage_token not in document or linkage_cue not in document:
        raise MobileReviewContractError("stage provenance state is not prominent and explicit")
    if 'class="stage-sheet"' not in document:
        raise MobileReviewContractError("mobile stage sheet presentation class is missing")

    lowered = document.lower()
    if "<script" in lowered or "http://" in lowered or "https://" in lowered:
        raise MobileReviewContractError("mobile review surface must remain script/network independent")


def validate_mobile_review_package(package: MobileReviewPackage) -> None:
    """Validate both static language pages and package-level safety metadata."""

    if not isinstance(package, MobileReviewPackage):
        raise MobileReviewContractError("package must be MobileReviewPackage")
    linkage = package.manifest.get("stage_linkage")
    if linkage not in ("separate-reference", "bundle-stage-artifacts"):
        raise MobileReviewContractError("package stage_linkage is invalid")
    presentation = package.manifest.get("presentation")
    if type(presentation) is not dict:
        raise MobileReviewContractError("package presentation record is missing")
    typed = cast(dict[str, object], presentation)
    if typed.get("scripts") != 0 or typed.get("external_dependencies") != 0:
        raise MobileReviewContractError("mobile package must stay script/external-dependency free")
    if typed.get("runtime_language_switch") is not False:
        raise MobileReviewContractError("language switching must remain static-page based")
    if typed.get("static_language_pages") != ["en", "ko"]:
        raise MobileReviewContractError("mobile package must publish exactly en and ko static pages")

    validate_mobile_review_surface(
        package.html_en,
        language="en",
        expected_stage_linkage=cast(str, linkage),
    )
    validate_mobile_review_surface(
        package.html_ko,
        language="ko",
        expected_stage_linkage=cast(str, linkage),
    )


def _require_positive_int(value: object, path: str) -> int:
    if type(value) is not int or value <= 0:
        raise MobileReviewContractError(f"{path} must be a positive integer")
    return cast(int, value)


def validate_mobile_review_proof(proof: object) -> None:
    """Validate one owner-recorded phone review proof without treating aesthetics as machine truth."""

    if type(proof) is not dict:
        raise MobileReviewContractError("proof must be a JSON object")
    record = cast(dict[str, object], proof)

    if record.get("schema") != MOBILE_REVIEW_PROOF_SCHEMA_V2:
        raise MobileReviewContractError(
            f"proof.schema must be {MOBILE_REVIEW_PROOF_SCHEMA_V2!r}"
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

    language = record.get("language")
    if language not in _LANGUAGE_PAGE:
        raise MobileReviewContractError("proof.language must be 'en' or 'ko'")
    expected_page = _LANGUAGE_PAGE[cast(str, language)]
    if record.get("review_page") != expected_page:
        raise MobileReviewContractError(
            f"proof.review_page must match proof.language: {expected_page!r}"
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
            "Build/validate the bilingual P6-V5 phone review package and, optionally, "
            "one owner-recorded mobile review proof."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional empty/non-existent directory to materialize the bilingual review package",
    )
    parser.add_argument(
        "--proof",
        type=Path,
        help="optional tracepixel.mobile-review-proof.v2 JSON record to validate",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    package = build_mobile_review_package(build_reference_gallery())
    validate_mobile_review_package(package)

    if args.output is not None:
        write_mobile_review_package(package, args.output)

    proof_state = "manual-proof-required"
    if args.proof is not None:
        proof = json.loads(args.proof.read_text(encoding="utf-8"))
        validate_mobile_review_proof(proof)
        proof_state = "manual-proof-valid"

    print(
        "P6-V5 mobile review checkpoint passed: "
        f"languages=en,ko stage_linkage={package.manifest['stage_linkage']} targets=5 "
        f"proof={proof_state} scripts=0 external_dependencies=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
