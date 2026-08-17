from __future__ import annotations

from copy import deepcopy
from typing import Mapping, Sequence, cast

from tracepixel.model import STAGE_SEQUENCE_V1
from tracepixel.repair import RepairEvidenceValidationError, validate_repair_evidence

from .b1_harness import (
    B1_FAILURE_TAXONOMY,
    B1_SCORED_METHOD_IDS,
    validate_b1_attempt_identity,
)

B1_ATTEMPT_RECORD_SCHEMA_V1 = "tracepixel.b1-attempt-record.v1"
B1_STAGE_COVERAGE_SCHEMA_V1 = "tracepixel.b1-stage-coverage.v1"
B1_REPAIR_LAYER_SCHEMA_V1 = "tracepixel.b1-repair-layer.v1"

B1_TRACEPIXEL_METHOD_ID = "tracepixel-post-p7-v1"
B1_RAW_METHOD_ID = "raw-pixel-program-v1"


class B1ScoredContractError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise B1ScoredContractError(code, path, message)


def _dict(value: object, path: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    raw = cast(dict[object, object], value)
    if not all(type(key) is str for key in raw):
        _fail("invalid_fields", path, "object keys must be strings")
    return cast(dict[str, object], raw)


def _assert_no_b0_result_reference(value: object, path: str) -> None:
    if type(value) is str:
        normalized = cast(str, value).replace("\\", "/").lower()
        if "evidence/b0/results/" in normalized:
            _fail(
                "b0_result_reference",
                path,
                "B1 scored evidence must not read, seed from, or substitute a B0 result path",
            )
        return
    if type(value) is list or type(value) is tuple:
        for index, item in enumerate(cast(Sequence[object], value)):
            _assert_no_b0_result_reference(item, f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, item in cast(dict[object, object], value).items():
            key_text = str(key)
            _assert_no_b0_result_reference(item, f"{path}.{key_text}")


def _validate_stage_decisions(value: object) -> dict[str, object]:
    if type(value) not in (list, tuple):
        _fail("invalid_type", "$stage_decisions", "must be an array")
    raw_items = list(cast(Sequence[object], value))
    if len(raw_items) > len(STAGE_SEQUENCE_V1):
        _fail("stage_count_exceeded", "$stage_decisions", "cannot contain more than the six frozen stages")

    decisions: list[dict[str, object]] = []
    applied = 0
    skipped = 0
    for index, item in enumerate(raw_items):
        path = f"$stage_decisions[{index}]"
        decision = _dict(item, path)
        required_fields = frozenset(("stage", "status", "skip_reason"))
        if frozenset(decision) != required_fields:
            _fail("invalid_fields", path, "stage decision fields must be stage/status/skip_reason")

        expected_stage = STAGE_SEQUENCE_V1[index]
        if decision.get("stage") != expected_stage:
            _fail("invalid_stage_order", f"{path}.stage", f"expected frozen stage {expected_stage!r}")

        status = decision.get("status")
        skip_reason = decision.get("skip_reason")
        if status == "applied":
            if skip_reason is not None:
                _fail("invalid_skip_reason", f"{path}.skip_reason", "applied stage must use null skip_reason")
            applied += 1
        elif status == "skipped":
            if type(skip_reason) is not str or not cast(str, skip_reason).strip() or len(cast(str, skip_reason)) > 128:
                _fail(
                    "invalid_skip_reason",
                    f"{path}.skip_reason",
                    "skipped stage requires a non-blank reason of at most 128 characters",
                )
            skipped += 1
        else:
            _fail("invalid_stage_status", f"{path}.status", "must be 'applied' or 'skipped'")
        decisions.append(deepcopy(decision))

    return {
        "schema": B1_STAGE_COVERAGE_SCHEMA_V1,
        "applicable": True,
        "required_stages": len(STAGE_SEQUENCE_V1),
        "decided_stages": len(decisions),
        "applied_stages": applied,
        "skipped_stages": skipped,
        "authoring_complete": len(decisions) == len(STAGE_SEQUENCE_V1),
        "stages": decisions,
    }


def _not_applicable_stage_coverage() -> dict[str, object]:
    return {
        "schema": B1_STAGE_COVERAGE_SCHEMA_V1,
        "applicable": False,
        "required_stages": None,
        "decided_stages": None,
        "applied_stages": None,
        "skipped_stages": None,
        "authoring_complete": None,
        "stages": [],
    }


def _repair_layer(method_id: str, repair_evidence: object | None) -> dict[str, object]:
    if repair_evidence is None:
        return {
            "schema": B1_REPAIR_LAYER_SCHEMA_V1,
            "applicable": method_id == B1_TRACEPIXEL_METHOD_ID,
            "available": False,
            "evidence": None,
        }
    if method_id != B1_TRACEPIXEL_METHOD_ID:
        _fail("raw_repair_forbidden", "$repair_evidence", "raw baseline has no TracePixel repair surface")
    _assert_no_b0_result_reference(repair_evidence, "$repair_evidence")
    try:
        validated = validate_repair_evidence(repair_evidence)
    except RepairEvidenceValidationError as exc:
        _fail(
            "invalid_repair_evidence",
            "$repair_evidence",
            f"P7 repair evidence rejected with {exc.code}: {exc.message}",
        )
    return {
        "schema": B1_REPAIR_LAYER_SCHEMA_V1,
        "applicable": True,
        "available": True,
        "evidence": deepcopy(validated),
    }


def build_b1_attempt_record(
    preregistration: Mapping[str, object],
    *,
    identity: object,
    completion: bool,
    failure_category: str | None,
    deterministic_qa: Mapping[str, object] | None,
    complexity: Mapping[str, object],
    stage_decisions: Sequence[Mapping[str, object]] = (),
    repair_evidence: object | None = None,
) -> dict[str, object]:
    """Build one B1 result layer without collapsing structural, stage, repair, or complexity evidence."""

    validated_identity = validate_b1_attempt_identity(identity, preregistration)
    method_id = cast(str, validated_identity["method_id"])
    if method_id not in B1_SCORED_METHOD_IDS:
        _fail("unknown_method", "$identity.method_id", method_id)
    if type(completion) is not bool:
        _fail("invalid_completion", "$completion", "must be a boolean")

    if completion:
        if failure_category is not None:
            _fail("failure_on_completion", "$failure_category", "completed attempts must use null failure_category")
        if deterministic_qa is None:
            _fail("missing_deterministic_qa", "$deterministic_qa", "completed attempts must retain deterministic QA")
    else:
        if failure_category not in B1_FAILURE_TAXONOMY:
            _fail("invalid_failure_category", "$failure_category", "non-completing attempts require the frozen failure taxonomy")

    qa_copy = None if deterministic_qa is None else deepcopy(_dict(deterministic_qa, "$deterministic_qa"))
    complexity_copy = deepcopy(_dict(complexity, "$complexity"))
    _assert_no_b0_result_reference(qa_copy, "$deterministic_qa")
    _assert_no_b0_result_reference(complexity_copy, "$complexity")

    if method_id == B1_TRACEPIXEL_METHOD_ID:
        coverage = _validate_stage_decisions(stage_decisions)
        if completion and coverage["authoring_complete"] is not True:
            _fail(
                "incomplete_stage_coverage",
                "$stage_decisions",
                "TracePixel cannot claim completion until all six stages are explicitly applied or skipped",
            )
    else:
        if stage_decisions:
            _fail("raw_stage_surface_forbidden", "$stage_decisions", "raw baseline must not receive TracePixel stage evidence")
        coverage = _not_applicable_stage_coverage()

    repair = _repair_layer(method_id, repair_evidence)

    return {
        "schema": B1_ATTEMPT_RECORD_SCHEMA_V1,
        "attempt": deepcopy(validated_identity),
        "completion": completion,
        "failure_category": failure_category,
        "deterministic_qa": qa_copy,
        "stage_coverage": coverage,
        "repair": repair,
        "complexity": complexity_copy,
    }
