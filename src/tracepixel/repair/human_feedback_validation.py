from __future__ import annotations

import json
from hashlib import sha256
from typing import cast

from .evidence import RepairEvidenceV1
from .evidence_validation import RepairEvidenceValidationError, validate_repair_evidence
from .feedback import FeedbackIntakeV1
from .feedback_validation import FeedbackIntakeValidationError, validate_feedback_intake
from .human_feedback import (
    HUMAN_FEEDBACK_SCHEMA_V1,
    MAX_HUMAN_REVIEW_SOURCE_CHARS_V1,
    MAX_HUMAN_REVIEW_SUMMARY_CHARS_V1,
    HumanFeedbackV1,
    HumanReviewDecisionV1,
)

_ROOT_FIELDS = frozenset(
    (
        "schema",
        "evidence",
        "evidence_manifest_sha256",
        "review",
        "feedback_intake",
        "completion",
        "authority",
    )
)
_REVIEW_FIELDS = frozenset(("source_ref", "decision", "summary"))
_COMPLETION_FIELDS = frozenset(
    ("deterministic_qa_status", "human_authoring_status", "composite_completion")
)
_AUTHORITY_FIELDS = frozenset(("human", "deterministic_qa", "perceptual", "vlm"))
_HEX_DIGITS = frozenset("0123456789abcdef")


class HumanFeedbackValidationError(ValueError):
    """Deterministic P7-F5 rejection with stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise HumanFeedbackValidationError(code, path, message)


def _require_exact_object(
    value: object,
    path: str,
    fields: frozenset[str],
) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    obj = cast(dict[object, object], value)
    if not all(type(key) is str for key in obj):
        _fail("invalid_fields", path, "object keys must be strings")
    typed = cast(dict[str, object], obj)
    actual = frozenset(typed)
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail("invalid_fields", path, "; ".join(parts))
    return typed


def _require_bounded_text(value: object, path: str, *, maximum: int) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    text = cast(str, value)
    if not text or len(text) > maximum:
        _fail("invalid_text", path, f"must contain 1..{maximum} characters")
    return text


def _require_digest(value: object, path: str) -> str:
    if (
        type(value) is not str
        or len(cast(str, value)) != 64
        or any(character not in _HEX_DIGITS for character in cast(str, value))
    ):
        _fail("invalid_digest", path, "must be 64 lowercase hexadecimal characters")
    return cast(str, value)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail("non_json_value", "$", f"must be canonical JSON-compatible data: {exc}")


def _validated_evidence(value: object) -> RepairEvidenceV1:
    try:
        return validate_repair_evidence(value)
    except RepairEvidenceValidationError as exc:
        path = "$.evidence" if exc.path == "$" else f"$.evidence{exc.path[1:]}"
        _fail(
            "invalid_evidence",
            path,
            f"repair evidence validation failed with {exc.code}: {exc.message}",
        )


def _validated_feedback_intake(value: object) -> FeedbackIntakeV1:
    try:
        return validate_feedback_intake(value)
    except FeedbackIntakeValidationError as exc:
        path = "$.feedback_intake" if exc.path == "$" else f"$.feedback_intake{exc.path[1:]}"
        _fail(
            "invalid_feedback_intake",
            path,
            f"feedback intake validation failed with {exc.code}: {exc.message}",
        )


def _validate_feedback_loop_target(
    intake: FeedbackIntakeV1,
    evidence: RepairEvidenceV1,
) -> None:
    evidence_target = evidence["execution"]["plan"]["localization"]["intake"]["target"]
    feedback_target = intake["target"]
    for key in ("asset_id", "task_id", "canvas"):
        if feedback_target[key] != evidence_target[key]:
            _fail(
                "feedback_target_mismatch",
                f"$.feedback_intake.target.{key}",
                "must match the exact reviewed F4 target",
            )
    if feedback_target["artifact_sha256"] != evidence["after_native_png"]["sha256"]:
        _fail(
            "feedback_artifact_mismatch",
            "$.feedback_intake.target.artifact_sha256",
            "must equal the exact reviewed F4 after/native.png SHA-256",
        )

    for index, item in enumerate(intake["items"]):
        path = f"$.feedback_intake.items[{index}]"
        if item["authority"] != "owner_human":
            _fail(
                "invalid_feedback_authority",
                f"{path}.authority",
                "F5 repair requests may only feed explicit owner-human items back into F0",
            )
        human = item["human"]
        if human is None or human["human_rejection"] is not True:
            _fail(
                "repair_request_not_rejected",
                f"{path}.human.human_rejection",
                "every F5 repair-request item must record explicit owner rejection",
            )


def validate_human_feedback(value: object) -> HumanFeedbackV1:
    """Validate one bounded repository-owner review over exact P7-F4 evidence."""

    root = _require_exact_object(value, "$", _ROOT_FIELDS)
    if root["schema"] != HUMAN_FEEDBACK_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"expected {HUMAN_FEEDBACK_SCHEMA_V1!r}",
        )

    evidence = _validated_evidence(root["evidence"])
    evidence_digest = _require_digest(root["evidence_manifest_sha256"], "$.evidence_manifest_sha256")
    expected_digest = sha256(_canonical_json_bytes(evidence)).hexdigest()
    if evidence_digest != expected_digest:
        _fail(
            "evidence_digest_mismatch",
            "$.evidence_manifest_sha256",
            "must equal the canonical reviewed F4 manifest SHA-256",
        )

    review = _require_exact_object(root["review"], "$.review", _REVIEW_FIELDS)
    _require_bounded_text(
        review["source_ref"],
        "$.review.source_ref",
        maximum=MAX_HUMAN_REVIEW_SOURCE_CHARS_V1,
    )
    decision = review["decision"]
    if decision not in ("accept", "request_repair"):
        _fail("invalid_decision", "$.review.decision", "must be 'accept' or 'request_repair'")
    _require_bounded_text(
        review["summary"],
        "$.review.summary",
        maximum=MAX_HUMAN_REVIEW_SUMMARY_CHARS_V1,
    )

    feedback_intake: FeedbackIntakeV1 | None
    if decision == "accept":
        if root["feedback_intake"] is not None:
            _fail(
                "accepted_with_feedback",
                "$.feedback_intake",
                "accepted evidence must not also request another repair loop",
            )
        feedback_intake = None
    else:
        if root["feedback_intake"] is None:
            _fail(
                "repair_feedback_required",
                "$.feedback_intake",
                "request_repair requires a bounded F0 feedback intake",
            )
        feedback_intake = _validated_feedback_intake(root["feedback_intake"])
        _validate_feedback_loop_target(feedback_intake, evidence)

    completion = _require_exact_object(root["completion"], "$.completion", _COMPLETION_FIELDS)
    expected_completion = {
        "deterministic_qa_status": (
            "findings-present" if evidence["execution"]["qa"]["findings"] else "no-findings"
        ),
        "human_authoring_status": "accepted" if decision == "accept" else "repair-requested",
        "composite_completion": "not-defined",
    }
    if completion != expected_completion:
        _fail(
            "completion_mismatch",
            "$.completion",
            "must preserve separate deterministic and human completion states with no composite result",
        )

    authority = _require_exact_object(root["authority"], "$.authority", _AUTHORITY_FIELDS)
    expected_authority = {
        "human": "repository-owner",
        "deterministic_qa": "retained-not-overridden",
        "perceptual": "owner-human-only",
        "vlm": "not-used",
    }
    if authority != expected_authority:
        _fail(
            "invalid_authority_boundary",
            "$.authority",
            "F5 records owner-human judgment without overriding deterministic QA or enabling VLM authority",
        )

    return cast(HumanFeedbackV1, value)


def create_human_feedback(
    evidence: object,
    *,
    source_ref: str,
    decision: HumanReviewDecisionV1,
    summary: str,
    feedback_intake: object | None = None,
) -> HumanFeedbackV1:
    """Create and validate one exact F5 owner-human review record."""

    validated_evidence = _validated_evidence(evidence)
    evidence_digest = sha256(_canonical_json_bytes(validated_evidence)).hexdigest()
    result: HumanFeedbackV1 = {
        "schema": HUMAN_FEEDBACK_SCHEMA_V1,
        "evidence": validated_evidence,
        "evidence_manifest_sha256": evidence_digest,
        "review": {
            "source_ref": source_ref,
            "decision": decision,
            "summary": summary,
        },
        "feedback_intake": cast(FeedbackIntakeV1 | None, feedback_intake),
        "completion": {
            "deterministic_qa_status": (
                "findings-present"
                if validated_evidence["execution"]["qa"]["findings"]
                else "no-findings"
            ),
            "human_authoring_status": "accepted" if decision == "accept" else "repair-requested",
            "composite_completion": "not-defined",
        },
        "authority": {
            "human": "repository-owner",
            "deterministic_qa": "retained-not-overridden",
            "perceptual": "owner-human-only",
            "vlm": "not-used",
        },
    }
    return validate_human_feedback(result)
