from __future__ import annotations

import copy
import json
from hashlib import sha256
from typing import Literal, cast

from tracepixel.raster.contract import CanvasSizeError, CanvasSpec
from tracepixel.repair.feedback import FEEDBACK_INTAKE_SCHEMA_V1, FeedbackIntakeV1
from tracepixel.repair.feedback_validation import (
    FeedbackIntakeValidationError,
    validate_feedback_intake,
)

OWNER_REVIEW_SESSION_SCHEMA_V1 = "tracepixel.owner-review-session.v1"
MAX_OWNER_REVIEW_ITEMS_V1 = 32
MAX_OWNER_REVIEW_TEXT_CHARS_V1 = 4096

OwnerReviewStateV1 = Literal[
    "experiment-frozen",
    "ready-for-owner-run",
    "running",
    "awaiting-owner-review",
    "accepted",
    "repair-requested",
    "rejected-stop",
]
OwnerReviewDecisionV1 = Literal["accept", "request_repair", "reject_stop"]
OwnerCriterionStatusV1 = Literal["accepted", "rejected", "unresolved"]

_STATES = frozenset(
    (
        "experiment-frozen",
        "ready-for-owner-run",
        "running",
        "awaiting-owner-review",
        "accepted",
        "repair-requested",
        "rejected-stop",
    )
)
_DECISIONS = frozenset(("accept", "request_repair", "reject_stop"))
_CRITERION_STATUSES = frozenset(("accepted", "rejected", "unresolved"))
_ROOT_FIELDS = frozenset(
    (
        "schema",
        "state",
        "experiment",
        "experiment_sha256",
        "owner_run_authorization",
        "run",
        "review_package",
        "owner_review",
        "feedback_intake",
        "authority",
    )
)
_EXPERIMENT_FIELDS = frozenset(
    (
        "experiment_id",
        "task_id",
        "asset_id",
        "canvas",
        "candidate_backends",
        "request_ref",
        "provider_model_ref",
        "deterministic_checks",
        "human_criteria",
        "retention_prefix",
        "budget",
    )
)
_BUDGET_FIELDS = (
    "max_provider_calls",
    "max_input_tokens",
    "max_output_tokens",
    "max_wall_ms",
    "max_repair_attempts",
    "max_regeneration_attempts",
)
_USAGE_TO_BUDGET = {
    "provider_calls": "max_provider_calls",
    "input_tokens": "max_input_tokens",
    "output_tokens": "max_output_tokens",
    "wall_ms": "max_wall_ms",
    "repair_attempts": "max_repair_attempts",
    "regeneration_attempts": "max_regeneration_attempts",
}
_EXPECTED_AUTHORITY = {
    "human": "repository-owner",
    "deterministic_qa": "retained-separate",
    "perceptual": "owner-human-only",
    "aesthetic_auto_accept": "forbidden",
}


class OwnerReviewValidationError(ValueError):
    """Fail-closed error for the P11-X1 owner-operated review protocol."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise OwnerReviewValidationError(code, path, message)


def _object(value: object, path: str, fields: frozenset[str] | None = None) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    result = cast(dict[str, object], value)
    if fields is not None and frozenset(result) != fields:
        _fail("invalid_fields", path, "object fields do not match the frozen contract")
    return result


def _array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def _text(value: object, path: str, *, maximum: int = 512) -> str:
    if type(value) is not str or not cast(str, value).strip() or len(cast(str, value)) > maximum:
        _fail("invalid_text", path, f"must contain 1..{maximum} non-blank characters")
    return cast(str, value)


def _non_negative_int(value: object, path: str) -> int:
    if type(value) is not int or cast(int, value) < 0:
        _fail("invalid_integer", path, "must be an exact non-negative integer")
    return cast(int, value)


def _digest(value: object, path: str) -> str:
    text = _text(value, path, maximum=64)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        _fail("invalid_digest", path, "must be 64 lowercase hexadecimal characters")
    return text


def _canonical_digest(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail("non_json_value", "$", f"must be canonical JSON-compatible data: {exc}")
    return sha256(encoded).hexdigest()


def _validate_unique_text_list(value: object, path: str, *, allow_empty: bool) -> list[str]:
    raw = _array(value, path)
    if not allow_empty and not raw:
        _fail("empty_list", path, "must contain at least one value")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        text = _text(item, f"{path}[{index}]", maximum=256)
        if text in seen:
            _fail("duplicate_value", f"{path}[{index}]", "values must be unique")
        seen.add(text)
        result.append(text)
    return result


def _validate_experiment(value: object) -> dict[str, object]:
    experiment = _object(value, "$.experiment", _EXPERIMENT_FIELDS)
    for field in ("experiment_id", "task_id", "asset_id"):
        _text(experiment[field], f"$.experiment.{field}", maximum=128)

    canvas = _object(experiment["canvas"], "$.experiment.canvas", frozenset(("width", "height")))
    try:
        CanvasSpec(canvas["width"], canvas["height"])
    except CanvasSizeError as exc:
        _fail("invalid_canvas", "$.experiment.canvas", str(exc))

    _validate_unique_text_list(
        experiment["candidate_backends"],
        "$.experiment.candidate_backends",
        allow_empty=False,
    )
    _text(experiment["request_ref"], "$.experiment.request_ref")
    _text(experiment["provider_model_ref"], "$.experiment.provider_model_ref")
    _validate_unique_text_list(
        experiment["deterministic_checks"],
        "$.experiment.deterministic_checks",
        allow_empty=True,
    )
    _text(experiment["retention_prefix"], "$.experiment.retention_prefix")

    criteria = _array(experiment["human_criteria"], "$.experiment.human_criteria")
    if not 1 <= len(criteria) <= MAX_OWNER_REVIEW_ITEMS_V1:
        _fail("invalid_criterion_count", "$.experiment.human_criteria", "criterion count is out of bounds")
    seen: set[str] = set()
    for index, raw in enumerate(criteria):
        criterion = _object(raw, f"$.experiment.human_criteria[{index}]", frozenset(("id", "description")))
        criterion_id = _text(criterion["id"], f"$.experiment.human_criteria[{index}].id", maximum=64)
        if criterion_id in seen:
            _fail("duplicate_criterion", f"$.experiment.human_criteria[{index}].id", "criterion ids must be unique")
        seen.add(criterion_id)
        _text(criterion["description"], f"$.experiment.human_criteria[{index}].description")

    budget = _object(experiment["budget"], "$.experiment.budget", frozenset(_BUDGET_FIELDS))
    for field in _BUDGET_FIELDS:
        _non_negative_int(budget[field], f"$.experiment.budget.{field}")
    return experiment


def _validate_run(value: object, experiment: dict[str, object]) -> dict[str, object]:
    fields = frozenset(("run_id", *_USAGE_TO_BUDGET.keys()))
    run = _object(value, "$.run", fields)
    _text(run["run_id"], "$.run.run_id", maximum=256)
    budget = cast(dict[str, object], experiment["budget"])
    for usage_field, budget_field in _USAGE_TO_BUDGET.items():
        amount = _non_negative_int(run[usage_field], f"$.run.{usage_field}")
        ceiling = cast(int, budget[budget_field])
        if amount > ceiling:
            _fail("budget_exceeded", f"$.run.{usage_field}", f"usage {amount} exceeds frozen {budget_field}={ceiling}")
    return run


def _validate_artifact(value: object, path: str) -> dict[str, object]:
    artifact = _object(value, path, frozenset(("ref", "sha256")))
    _text(artifact["ref"], f"{path}.ref", maximum=1024)
    _digest(artifact["sha256"], f"{path}.sha256")
    return artifact


def _validate_package(value: object, experiment: dict[str, object]) -> dict[str, object]:
    fields = frozenset(
        (
            "candidate_id",
            "backend",
            "candidate_rgba_sha256",
            "native_png",
            "preview_png",
            "deterministic_qa_evidence",
            "complexity_evidence",
        )
    )
    package = _object(value, "$.review_package", fields)
    _text(package["candidate_id"], "$.review_package.candidate_id", maximum=256)
    backend = _text(package["backend"], "$.review_package.backend", maximum=256)
    if backend not in cast(list[str], experiment["candidate_backends"]):
        _fail("unfrozen_backend", "$.review_package.backend", "backend was not preregistered")
    _digest(package["candidate_rgba_sha256"], "$.review_package.candidate_rgba_sha256")
    for field in ("native_png", "preview_png", "deterministic_qa_evidence", "complexity_evidence"):
        _validate_artifact(package[field], f"$.review_package.{field}")
    return package


def _validate_review(
    value: object,
    experiment: dict[str, object],
    run: dict[str, object],
    package: dict[str, object],
) -> dict[str, object]:
    fields = frozenset(
        (
            "source_ref",
            "decision",
            "summary",
            "reviewed_run_id",
            "reviewed_candidate_id",
            "reviewed_native_png_sha256",
            "criteria",
        )
    )
    review = _object(value, "$.owner_review", fields)
    _text(review["source_ref"], "$.owner_review.source_ref")
    if review["decision"] not in _DECISIONS:
        _fail("invalid_decision", "$.owner_review.decision", "unsupported owner decision")
    _text(review["summary"], "$.owner_review.summary", maximum=MAX_OWNER_REVIEW_TEXT_CHARS_V1)
    if review["reviewed_run_id"] != run["run_id"]:
        _fail("review_run_mismatch", "$.owner_review.reviewed_run_id", "must bind the exact reviewed run")
    if review["reviewed_candidate_id"] != package["candidate_id"]:
        _fail("review_candidate_mismatch", "$.owner_review.reviewed_candidate_id", "must bind the exact candidate")
    native = cast(dict[str, object], package["native_png"])
    if review["reviewed_native_png_sha256"] != native["sha256"]:
        _fail("review_artifact_mismatch", "$.owner_review.reviewed_native_png_sha256", "must bind the exact native PNG")

    frozen_ids = [cast(dict[str, object], item)["id"] for item in cast(list[object], experiment["human_criteria"])]
    criteria = _array(review["criteria"], "$.owner_review.criteria")
    if len(criteria) != len(frozen_ids):
        _fail("criterion_set_mismatch", "$.owner_review.criteria", "must retain every frozen criterion")
    for index, raw in enumerate(criteria):
        item = _object(raw, f"$.owner_review.criteria[{index}]", frozenset(("id", "status")))
        if item["id"] != frozen_ids[index] or item["status"] not in _CRITERION_STATUSES:
            _fail("criterion_set_mismatch", f"$.owner_review.criteria[{index}]", "criterion identity/status is invalid")
    return review


def _validate_feedback(
    value: object,
    experiment: dict[str, object],
    package: dict[str, object],
) -> FeedbackIntakeV1:
    try:
        intake = validate_feedback_intake(value)
    except FeedbackIntakeValidationError as exc:
        _fail("invalid_feedback_intake", "$.feedback_intake", f"P7 feedback intake failed with {exc.code}: {exc.message}")

    target = intake["target"]
    canvas = cast(dict[str, int], experiment["canvas"])
    native = cast(dict[str, object], package["native_png"])
    if (
        target["asset_id"] != experiment["asset_id"]
        or target["task_id"] != experiment["task_id"]
        or target["canvas"] != canvas
        or target["artifact_sha256"] != native["sha256"]
    ):
        _fail("feedback_target_mismatch", "$.feedback_intake.target", "must bind the exact reviewed artifact")
    for index, item in enumerate(intake["items"]):
        human = item["human"]
        if item["authority"] != "owner_human" or human is None or human["human_rejection"] is not True:
            _fail("feedback_authority_mismatch", f"$.feedback_intake.items[{index}]", "must retain explicit owner-human rejection")
    return intake


def validate_owner_review_session(value: object) -> dict[str, object]:
    """Validate one recoverable owner-review session without inferring aesthetics."""

    root = _object(value, "$", _ROOT_FIELDS)
    if root["schema"] != OWNER_REVIEW_SESSION_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {OWNER_REVIEW_SESSION_SCHEMA_V1!r}")
    if root["state"] not in _STATES:
        _fail("invalid_state", "$.state", "unsupported owner-review state")

    experiment = _validate_experiment(root["experiment"])
    if _digest(root["experiment_sha256"], "$.experiment_sha256") != _canonical_digest(experiment):
        _fail("experiment_digest_mismatch", "$.experiment_sha256", "frozen experiment changed after preregistration")
    if root["authority"] != _EXPECTED_AUTHORITY:
        _fail("authority_boundary_mismatch", "$.authority", "human and deterministic authority must remain separate")

    authorization = root["owner_run_authorization"]
    if authorization is not None:
        authorization = _object(authorization, "$.owner_run_authorization", frozenset(("source_ref",)))
        _text(authorization["source_ref"], "$.owner_run_authorization.source_ref")

    run = None if root["run"] is None else _validate_run(root["run"], experiment)
    package = None if root["review_package"] is None else _validate_package(root["review_package"], experiment)
    review = None
    if root["owner_review"] is not None:
        if run is None or package is None:
            _fail("review_without_package", "$.owner_review", "owner review requires an exact run/package")
        review = _validate_review(root["owner_review"], experiment, run, package)
    feedback = None
    if root["feedback_intake"] is not None:
        if package is None:
            _fail("feedback_without_package", "$.feedback_intake", "feedback requires an exact review package")
        feedback = _validate_feedback(root["feedback_intake"], experiment, package)

    state = cast(str, root["state"])
    if state == "experiment-frozen":
        valid = authorization is None and run is None and package is None and review is None and feedback is None
    elif state in ("ready-for-owner-run", "running"):
        valid = authorization is not None and run is None and package is None and review is None and feedback is None
    elif state == "awaiting-owner-review":
        valid = authorization is not None and run is not None and package is not None and review is None and feedback is None
    elif state == "accepted":
        valid = authorization is not None and run is not None and package is not None and review is not None and feedback is None and review["decision"] == "accept"
    elif state == "rejected-stop":
        valid = authorization is not None and run is not None and package is not None and review is not None and feedback is None and review["decision"] == "reject_stop"
    else:
        valid = authorization is not None and run is not None and package is not None and review is not None and feedback is not None and review["decision"] == "request_repair"
        if valid:
            budget = cast(dict[str, object], experiment["budget"])
            valid = cast(int, run["repair_attempts"]) < cast(int, budget["max_repair_attempts"])
            if not valid:
                _fail("repair_budget_exhausted", "$.run.repair_attempts", "preregistered repair budget is exhausted")
    if not valid:
        _fail("state_payload_mismatch", "$", f"payload does not match state {state!r}")
    return root


def freeze_owner_experiment(
    *,
    experiment_id: str,
    task_id: str,
    asset_id: str,
    width: int,
    height: int,
    candidate_backends: list[str],
    request_ref: str,
    provider_model_ref: str,
    deterministic_checks: list[str],
    human_criteria: list[dict[str, str]],
    retention_prefix: str,
    budget: dict[str, int],
) -> dict[str, object]:
    """Preregister one experiment before any paid/provider execution begins."""

    experiment: dict[str, object] = {
        "experiment_id": experiment_id,
        "task_id": task_id,
        "asset_id": asset_id,
        "canvas": {"width": width, "height": height},
        "candidate_backends": copy.deepcopy(candidate_backends),
        "request_ref": request_ref,
        "provider_model_ref": provider_model_ref,
        "deterministic_checks": copy.deepcopy(deterministic_checks),
        "human_criteria": copy.deepcopy(human_criteria),
        "retention_prefix": retention_prefix,
        "budget": copy.deepcopy(budget),
    }
    session: dict[str, object] = {
        "schema": OWNER_REVIEW_SESSION_SCHEMA_V1,
        "state": "experiment-frozen",
        "experiment": experiment,
        "experiment_sha256": _canonical_digest(experiment),
        "owner_run_authorization": None,
        "run": None,
        "review_package": None,
        "owner_review": None,
        "feedback_intake": None,
        "authority": copy.deepcopy(_EXPECTED_AUTHORITY),
    }
    return validate_owner_review_session(session)


def authorize_owner_run(session: object, *, source_ref: str) -> dict[str, object]:
    """Record explicit owner authorization before a bounded run may begin."""

    current = validate_owner_review_session(session)
    if current["state"] != "experiment-frozen":
        _fail("invalid_transition", "$.state", "owner authorization requires experiment-frozen state")
    result = copy.deepcopy(current)
    result["state"] = "ready-for-owner-run"
    result["owner_run_authorization"] = {"source_ref": source_ref}
    return validate_owner_review_session(result)


def begin_owner_run(session: object) -> dict[str, object]:
    """Enter running only after explicit owner authorization."""

    current = validate_owner_review_session(session)
    if current["state"] != "ready-for-owner-run":
        _fail("invalid_transition", "$.state", "run may begin only from ready-for-owner-run")
    result = copy.deepcopy(current)
    result["state"] = "running"
    return validate_owner_review_session(result)


def attach_owner_review_package(
    session: object,
    *,
    run: dict[str, object],
    candidate_id: str,
    backend: str,
    candidate_rgba_sha256: str,
    native_png: dict[str, str],
    preview_png: dict[str, str],
    deterministic_qa_evidence: dict[str, str],
    complexity_evidence: dict[str, str],
) -> dict[str, object]:
    """Freeze exact evidence and enter the mandatory awaiting-owner-review stop."""

    current = validate_owner_review_session(session)
    if current["state"] != "running":
        _fail("invalid_transition", "$.state", "review package may attach only to a running session")
    result = copy.deepcopy(current)
    result["run"] = copy.deepcopy(run)
    result["review_package"] = {
        "candidate_id": candidate_id,
        "backend": backend,
        "candidate_rgba_sha256": candidate_rgba_sha256,
        "native_png": copy.deepcopy(native_png),
        "preview_png": copy.deepcopy(preview_png),
        "deterministic_qa_evidence": copy.deepcopy(deterministic_qa_evidence),
        "complexity_evidence": copy.deepcopy(complexity_evidence),
    }
    result["state"] = "awaiting-owner-review"
    return validate_owner_review_session(result)


def record_owner_review(
    session: object,
    *,
    source_ref: str,
    decision: OwnerReviewDecisionV1,
    summary: str,
    criterion_statuses: dict[str, OwnerCriterionStatusV1] | None = None,
    repair_feedback: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Bind owner judgment exactly; missing criteria/regions/stages remain unresolved/null."""

    current = validate_owner_review_session(session)
    if current["state"] != "awaiting-owner-review":
        _fail("invalid_transition", "$.state", "owner review requires awaiting-owner-review state")
    if decision not in _DECISIONS:
        _fail("invalid_decision", "$.owner_review.decision", "unsupported owner decision")

    experiment = cast(dict[str, object], current["experiment"])
    run = cast(dict[str, object], current["run"])
    package = cast(dict[str, object], current["review_package"])
    frozen_ids = [cast(dict[str, object], item)["id"] for item in cast(list[object], experiment["human_criteria"])]
    explicit = criterion_statuses or {}
    unknown = sorted(set(explicit) - set(cast(list[str], frozen_ids)))
    if unknown:
        _fail("unknown_criterion", "$.owner_review.criteria", f"unfrozen criteria supplied: {unknown}")
    for criterion_id, status in explicit.items():
        if status not in _CRITERION_STATUSES:
            _fail("invalid_criterion_status", f"$.owner_review.criteria.{criterion_id}", "unsupported criterion status")

    native = cast(dict[str, object], package["native_png"])
    result = copy.deepcopy(current)
    result["owner_review"] = {
        "source_ref": source_ref,
        "decision": decision,
        "summary": summary,
        "reviewed_run_id": run["run_id"],
        "reviewed_candidate_id": package["candidate_id"],
        "reviewed_native_png_sha256": native["sha256"],
        "criteria": [
            {"id": criterion_id, "status": explicit.get(cast(str, criterion_id), "unresolved")}
            for criterion_id in frozen_ids
        ],
    }

    if decision in ("accept", "reject_stop"):
        if repair_feedback:
            _fail("unexpected_repair_feedback", "$.feedback_intake", "this decision must not request repair")
        result["feedback_intake"] = None
        result["state"] = "accepted" if decision == "accept" else "rejected-stop"
        return validate_owner_review_session(result)

    if not repair_feedback:
        _fail("repair_feedback_required", "$.feedback_intake", "request_repair requires explicit owner feedback")
    budget = cast(dict[str, object], experiment["budget"])
    if cast(int, run["repair_attempts"]) >= cast(int, budget["max_repair_attempts"]):
        _fail("repair_budget_exhausted", "$.run.repair_attempts", "preregistered repair budget is exhausted")

    items: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, feedback in enumerate(repair_feedback):
        feedback_id = _text(feedback.get("id"), f"$.repair_feedback[{index}].id", maximum=64)
        if feedback_id in seen:
            _fail("duplicate_feedback_id", f"$.repair_feedback[{index}].id", "feedback ids must be unique")
        seen.add(feedback_id)
        feedback_summary = _text(feedback.get("summary"), f"$.repair_feedback[{index}].summary")
        items.append(
            {
                "id": feedback_id,
                "authority": "owner_human",
                "source_ref": source_ref,
                "summary": feedback_summary,
                "stage_hint": copy.deepcopy(feedback.get("stage_hint")),
                "region_hint": copy.deepcopy(feedback.get("region_hint")),
                "deterministic_qa": None,
                "human": {"human_rejection": True, "scores": []},
            }
        )

    intake: FeedbackIntakeV1 = {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": cast(str, experiment["asset_id"]),
            "task_id": cast(str, experiment["task_id"]),
            "canvas": cast(dict[str, int], copy.deepcopy(experiment["canvas"])),
            "artifact_sha256": cast(str, native["sha256"]),
        },
        "items": cast(list, items),
    }
    result["feedback_intake"] = validate_feedback_intake(intake)
    result["state"] = "repair-requested"
    return validate_owner_review_session(result)


__all__ = [
    "OWNER_REVIEW_SESSION_SCHEMA_V1",
    "OwnerReviewDecisionV1",
    "OwnerReviewStateV1",
    "OwnerReviewValidationError",
    "attach_owner_review_package",
    "authorize_owner_run",
    "begin_owner_run",
    "freeze_owner_experiment",
    "record_owner_review",
    "validate_owner_review_session",
]
