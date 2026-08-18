from __future__ import annotations

import copy
import json
from hashlib import sha256
from typing import Literal, TypedDict, cast

from tracepixel.model.stage_plan import StageIdV1
from tracepixel.raster.contract import CanvasSizeError, CanvasSpec
from tracepixel.repair.feedback import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    FeedbackIntakeV1,
    FeedbackRegionV1,
)
from tracepixel.repair.feedback_validation import (
    FeedbackIntakeValidationError,
    validate_feedback_intake,
)

OWNER_REVIEW_SESSION_SCHEMA_V1 = "tracepixel.owner-review-session.v1"
MAX_OWNER_REVIEW_TEXT_CHARS_V1 = 4096
MAX_OWNER_REVIEW_ITEMS_V1 = 32

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


class OwnerReviewCriterionV1(TypedDict):
    id: str
    description: str


class OwnerReviewBudgetV1(TypedDict):
    max_provider_calls: int
    max_input_tokens: int
    max_output_tokens: int
    max_wall_ms: int
    max_repair_attempts: int
    max_regeneration_attempts: int


class OwnerReviewExperimentV1(TypedDict):
    experiment_id: str
    task_id: str
    asset_id: str
    canvas: dict[str, int]
    candidate_backends: list[str]
    request_ref: str
    provider_model_ref: str
    deterministic_checks: list[str]
    human_criteria: list[OwnerReviewCriterionV1]
    retention_prefix: str
    budget: OwnerReviewBudgetV1


class OwnerRunAuthorizationV1(TypedDict):
    source_ref: str


class OwnerRunUsageV1(TypedDict):
    run_id: str
    provider_calls: int
    input_tokens: int
    output_tokens: int
    wall_ms: int
    repair_attempts: int
    regeneration_attempts: int


class OwnerReviewArtifactV1(TypedDict):
    ref: str
    sha256: str


class OwnerReviewPackageV1(TypedDict):
    candidate_id: str
    backend: str
    candidate_rgba_sha256: str
    native_png: OwnerReviewArtifactV1
    preview_png: OwnerReviewArtifactV1
    deterministic_qa_evidence: OwnerReviewArtifactV1
    complexity_evidence: OwnerReviewArtifactV1


class OwnerCriterionReviewV1(TypedDict):
    id: str
    status: OwnerCriterionStatusV1


class OwnerReviewDecisionRecordV1(TypedDict):
    source_ref: str
    decision: OwnerReviewDecisionV1
    summary: str
    reviewed_run_id: str
    reviewed_candidate_id: str
    reviewed_native_png_sha256: str
    criteria: list[OwnerCriterionReviewV1]


class OwnerReviewAuthorityV1(TypedDict):
    human: Literal["repository-owner"]
    deterministic_qa: Literal["retained-separate"]
    perceptual: Literal["owner-human-only"]
    aesthetic_auto_accept: Literal["forbidden"]


class OwnerRepairFeedbackInputV1(TypedDict):
    id: str
    summary: str
    stage_hint: StageIdV1 | None
    region_hint: FeedbackRegionV1 | None


class OwnerReviewSessionV1(TypedDict):
    schema: Literal["tracepixel.owner-review-session.v1"]
    state: OwnerReviewStateV1
    experiment: OwnerReviewExperimentV1
    experiment_sha256: str
    owner_run_authorization: OwnerRunAuthorizationV1 | None
    run: OwnerRunUsageV1 | None
    review_package: OwnerReviewPackageV1 | None
    owner_review: OwnerReviewDecisionRecordV1 | None
    feedback_intake: FeedbackIntakeV1 | None
    authority: OwnerReviewAuthorityV1


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
_CANVAS_FIELDS = frozenset(("width", "height"))
_CRITERION_FIELDS = frozenset(("id", "description"))
_BUDGET_FIELDS = frozenset(
    (
        "max_provider_calls",
        "max_input_tokens",
        "max_output_tokens",
        "max_wall_ms",
        "max_repair_attempts",
        "max_regeneration_attempts",
    )
)
_AUTHORIZATION_FIELDS = frozenset(("source_ref",))
_RUN_FIELDS = frozenset(
    (
        "run_id",
        "provider_calls",
        "input_tokens",
        "output_tokens",
        "wall_ms",
        "repair_attempts",
        "regeneration_attempts",
    )
)
_PACKAGE_FIELDS = frozenset(
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
_ARTIFACT_FIELDS = frozenset(("ref", "sha256"))
_REVIEW_FIELDS = frozenset(
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
_CRITERION_REVIEW_FIELDS = frozenset(("id", "status"))
_AUTHORITY_FIELDS = frozenset(("human", "deterministic_qa", "perceptual", "aesthetic_auto_accept"))
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
_HEX_DIGITS = frozenset("0123456789abcdef")


class OwnerReviewValidationError(ValueError):
    """Stable fail-closed error for the P11-X1 owner-operated review protocol."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise OwnerReviewValidationError(code, path, message)


def _require_exact_object(value: object, path: str, fields: frozenset[str]) -> dict[str, object]:
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


def _require_array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def _require_text(value: object, path: str, *, maximum: int = 512) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    text = cast(str, value)
    if not text.strip() or len(text) > maximum:
        _fail("invalid_text", path, f"must contain 1..{maximum} non-blank characters")
    return text


def _require_non_negative_int(value: object, path: str) -> int:
    if type(value) is not int or cast(int, value) < 0:
        _fail("invalid_integer", path, "must be an exact non-negative integer")
    return cast(int, value)


def _require_digest(value: object, path: str) -> str:
    if (
        type(value) is not str
        or len(cast(str, value)) != 64
        or any(character not in _HEX_DIGITS for character in cast(str, value))
    ):
        _fail("invalid_digest", path, "must be 64 lowercase hexadecimal characters")
    return cast(str, value)


def _canonical_digest(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail("non_json_value", "$", f"must be canonical JSON-compatible data: {exc}")
    return sha256(payload).hexdigest()


def _validate_string_list(value: object, path: str, *, allow_empty: bool) -> list[str]:
    raw = _require_array(value, path)
    if not allow_empty and not raw:
        _fail("empty_list", path, "must contain at least one value")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        text = _require_text(item, f"{path}[{index}]", maximum=256)
        if text in seen:
            _fail("duplicate_value", f"{path}[{index}]", "values must be unique")
        seen.add(text)
        result.append(text)
    return result


def _validate_experiment(value: object) -> OwnerReviewExperimentV1:
    experiment = _require_exact_object(value, "$.experiment", _EXPERIMENT_FIELDS)
    _require_text(experiment["experiment_id"], "$.experiment.experiment_id", maximum=128)
    _require_text(experiment["task_id"], "$.experiment.task_id", maximum=128)
    _require_text(experiment["asset_id"], "$.experiment.asset_id", maximum=128)

    canvas = _require_exact_object(experiment["canvas"], "$.experiment.canvas", _CANVAS_FIELDS)
    try:
        CanvasSpec(canvas["width"], canvas["height"])
    except CanvasSizeError as exc:
        _fail("invalid_canvas", "$.experiment.canvas", str(exc))

    _validate_string_list(experiment["candidate_backends"], "$.experiment.candidate_backends", allow_empty=False)
    _require_text(experiment["request_ref"], "$.experiment.request_ref", maximum=512)
    _require_text(experiment["provider_model_ref"], "$.experiment.provider_model_ref", maximum=512)
    _validate_string_list(experiment["deterministic_checks"], "$.experiment.deterministic_checks", allow_empty=True)
    _require_text(experiment["retention_prefix"], "$.experiment.retention_prefix", maximum=512)

    criteria = _require_array(experiment["human_criteria"], "$.experiment.human_criteria")
    if not 1 <= len(criteria) <= MAX_OWNER_REVIEW_ITEMS_V1:
        _fail(
            "invalid_criterion_count",
            "$.experiment.human_criteria",
            f"must contain 1..{MAX_OWNER_REVIEW_ITEMS_V1} criteria",
        )
    seen_criteria: set[str] = set()
    for index, raw_criterion in enumerate(criteria):
        path = f"$.experiment.human_criteria[{index}]"
        criterion = _require_exact_object(raw_criterion, path, _CRITERION_FIELDS)
        criterion_id = _require_text(criterion["id"], f"{path}.id", maximum=64)
        if criterion_id in seen_criteria:
            _fail("duplicate_criterion", f"{path}.id", "criterion ids must be unique")
        seen_criteria.add(criterion_id)
        _require_text(criterion["description"], f"{path}.description", maximum=512)

    budget = _require_exact_object(experiment["budget"], "$.experiment.budget", _BUDGET_FIELDS)
    for field in _BUDGET_FIELDS:
        _require_non_negative_int(budget[field], f"$.experiment.budget.{field}")

    return cast(OwnerReviewExperimentV1, value)


def _validate_artifact(value: object, path: str) -> OwnerReviewArtifactV1:
    artifact = _require_exact_object(value, path, _ARTIFACT_FIELDS)
    _require_text(artifact["ref"], f"{path}.ref", maximum=1024)
    _require_digest(artifact["sha256"], f"{path}.sha256")
    return cast(OwnerReviewArtifactV1, value)


def _validate_run(value: object, experiment: OwnerReviewExperimentV1) -> OwnerRunUsageV1:
    run = _require_exact_object(value, "$.run", _RUN_FIELDS)
    _require_text(run["run_id"], "$.run.run_id", maximum=256)
    budget = experiment["budget"]
    usage_to_budget = {
        "provider_calls": "max_provider_calls",
        "input_tokens": "max_input_tokens",
        "output_tokens": "max_output_tokens",
        "wall_ms": "max_wall_ms",
        "repair_attempts": "max_repair_attempts",
        "regeneration_attempts": "max_regeneration_attempts",
    }
    for usage_field, budget_field in usage_to_budget.items():
        amount = _require_non_negative_int(run[usage_field], f"$.run.{usage_field}")
        if amount > budget[cast(str, budget_field)]:
            _fail(
                "budget_exceeded",
                f"$.run.{usage_field}",
                f"usage {amount} exceeds frozen {budget_field}={budget[cast(str, budget_field)]}",
            )
    return cast(OwnerRunUsageV1, value)


def _validate_package(value: object, experiment: OwnerReviewExperimentV1) -> OwnerReviewPackageV1:
    package = _require_exact_object(value, "$.review_package", _PACKAGE_FIELDS)
    _require_text(package["candidate_id"], "$.review_package.candidate_id", maximum=256)
    backend = _require_text(package["backend"], "$.review_package.backend", maximum=256)
    if backend not in experiment["candidate_backends"]:
        _fail(
            "unfrozen_backend",
            "$.review_package.backend",
            "backend must be one of the preregistered candidate backends",
        )
    _require_digest(package["candidate_rgba_sha256"], "$.review_package.candidate_rgba_sha256")
    for field in (
        "native_png",
        "preview_png",
        "deterministic_qa_evidence",
        "complexity_evidence",
    ):
        _validate_artifact(package[field], f"$.review_package.{field}")
    return cast(OwnerReviewPackageV1, value)


def _validate_owner_review(
    value: object,
    experiment: OwnerReviewExperimentV1,
    run: OwnerRunUsageV1,
    package: OwnerReviewPackageV1,
) -> OwnerReviewDecisionRecordV1:
    review = _require_exact_object(value, "$.owner_review", _REVIEW_FIELDS)
    _require_text(review["source_ref"], "$.owner_review.source_ref", maximum=512)
    decision = review["decision"]
    if decision not in _DECISIONS:
        _fail("invalid_decision", "$.owner_review.decision", "unsupported owner review decision")
    _require_text(
        review["summary"],
        "$.owner_review.summary",
        maximum=MAX_OWNER_REVIEW_TEXT_CHARS_V1,
    )
    if review["reviewed_run_id"] != run["run_id"]:
        _fail("review_run_mismatch", "$.owner_review.reviewed_run_id", "must bind the exact reviewed run")
    if review["reviewed_candidate_id"] != package["candidate_id"]:
        _fail(
            "review_candidate_mismatch",
            "$.owner_review.reviewed_candidate_id",
            "must bind the exact reviewed candidate",
        )
    if review["reviewed_native_png_sha256"] != package["native_png"]["sha256"]:
        _fail(
            "review_artifact_mismatch",
            "$.owner_review.reviewed_native_png_sha256",
            "must bind the exact reviewed native PNG digest",
        )

    frozen_ids = [criterion["id"] for criterion in experiment["human_criteria"]]
    raw_criteria = _require_array(review["criteria"], "$.owner_review.criteria")
    if len(raw_criteria) != len(frozen_ids):
        _fail(
            "criterion_set_mismatch",
            "$.owner_review.criteria",
            "must record every frozen criterion exactly once",
        )
    for index, raw_criterion in enumerate(raw_criteria):
        path = f"$.owner_review.criteria[{index}]"
        criterion = _require_exact_object(raw_criterion, path, _CRITERION_REVIEW_FIELDS)
        if criterion["id"] != frozen_ids[index]:
            _fail(
                "criterion_set_mismatch",
                f"{path}.id",
                "criterion order and identity must match the frozen experiment",
            )
        if criterion["status"] not in _CRITERION_STATUSES:
            _fail("invalid_criterion_status", f"{path}.status", "unsupported criterion status")

    return cast(OwnerReviewDecisionRecordV1, value)


def _validate_feedback_binding(
    value: object,
    experiment: OwnerReviewExperimentV1,
    package: OwnerReviewPackageV1,
) -> FeedbackIntakeV1:
    try:
        intake = validate_feedback_intake(value)
    except FeedbackIntakeValidationError as exc:
        path = "$.feedback_intake" if exc.path == "$" else f"$.feedback_intake{exc.path[1:]}"
        _fail("invalid_feedback_intake", path, f"P7 feedback intake failed with {exc.code}: {exc.message}")

    target = intake["target"]
    if target["asset_id"] != experiment["asset_id"] or target["task_id"] != experiment["task_id"]:
        _fail(
            "feedback_target_mismatch",
            "$.feedback_intake.target",
            "must bind the exact frozen asset/task identity",
        )
    if target["canvas"] != experiment["canvas"]:
        _fail(
            "feedback_canvas_mismatch",
            "$.feedback_intake.target.canvas",
            "must bind the exact frozen canvas",
        )
    if target["artifact_sha256"] != package["native_png"]["sha256"]:
        _fail(
            "feedback_artifact_mismatch",
            "$.feedback_intake.target.artifact_sha256",
            "must bind the exact reviewed native PNG digest",
        )
    for index, item in enumerate(intake["items"]):
        if item["authority"] != "owner_human":
            _fail(
                "feedback_authority_mismatch",
                f"$.feedback_intake.items[{index}].authority",
                "owner review feedback must retain owner_human authority",
            )
        human = item["human"]
        if human is None or human["human_rejection"] is not True:
            _fail(
                "feedback_rejection_required",
                f"$.feedback_intake.items[{index}].human.human_rejection",
                "repair feedback must record explicit owner rejection",
            )
    return intake


def validate_owner_review_session(value: object) -> OwnerReviewSessionV1:
    """Validate one recoverable P11-X1 session without inferring aesthetic truth."""

    root = _require_exact_object(value, "$", _ROOT_FIELDS)
    if root["schema"] != OWNER_REVIEW_SESSION_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {OWNER_REVIEW_SESSION_SCHEMA_V1!r}")
    state = root["state"]
    if state not in _STATES:
        _fail("invalid_state", "$.state", "unsupported owner review state")

    experiment = _validate_experiment(root["experiment"])
    experiment_digest = _require_digest(root["experiment_sha256"], "$.experiment_sha256")
    if experiment_digest != _canonical_digest(experiment):
        _fail(
            "experiment_digest_mismatch",
            "$.experiment_sha256",
            "frozen experiment contents changed after preregistration",
        )

    expected_authority = {
        "human": "repository-owner",
        "deterministic_qa": "retained-separate",
        "perceptual": "owner-human-only",
        "aesthetic_auto_accept": "forbidden",
    }
    authority = _require_exact_object(root["authority"], "$.authority", _AUTHORITY_FIELDS)
    if authority != expected_authority:
        _fail(
            "authority_boundary_mismatch",
            "$.authority",
            "owner aesthetics and deterministic QA must remain separate",
        )

    authorization: OwnerRunAuthorizationV1 | None = None
    if root["owner_run_authorization"] is not None:
        raw_authorization = _require_exact_object(
            root["owner_run_authorization"],
            "$.owner_run_authorization",
            _AUTHORIZATION_FIELDS,
        )
        _require_text(raw_authorization["source_ref"], "$.owner_run_authorization.source_ref", maximum=512)
        authorization = cast(OwnerRunAuthorizationV1, root["owner_run_authorization"])

    run: OwnerRunUsageV1 | None = None
    if root["run"] is not None:
        run = _validate_run(root["run"], experiment)

    package: OwnerReviewPackageV1 | None = None
    if root["review_package"] is not None:
        package = _validate_package(root["review_package"], experiment)

    review: OwnerReviewDecisionRecordV1 | None = None
    if root["owner_review"] is not None:
        if run is None or package is None:
            _fail("review_without_package", "$.owner_review", "owner review requires an exact retained run/package")
        review = _validate_owner_review(root["owner_review"], experiment, run, package)

    feedback: FeedbackIntakeV1 | None = None
    if root["feedback_intake"] is not None:
        if package is None:
            _fail("feedback_without_package", "$.feedback_intake", "feedback requires an exact reviewed package")
        feedback = _validate_feedback_binding(root["feedback_intake"], experiment, package)

    if state == "experiment-frozen":
        if any(item is not None for item in (authorization, run, package, review, feedback)):
            _fail("state_payload_mismatch", "$", "experiment-frozen must not contain later-state payloads")
    elif state == "ready-for-owner-run":
        if authorization is None or any(item is not None for item in (run, package, review, feedback)):
            _fail("state_payload_mismatch", "$", "ready-for-owner-run requires only owner authorization")
    elif state == "running":
        if authorization is None or any(item is not None for item in (run, package, review, feedback)):
            _fail("state_payload_mismatch", "$", "running requires prior owner authorization and no result yet")
    elif state == "awaiting-owner-review":
        if authorization is None or run is None or package is None or review is not None or feedback is not None:
            _fail(
                "state_payload_mismatch",
                "$",
                "awaiting-owner-review requires exact run/package and must stop before owner feedback",
            )
    elif state == "accepted":
        if authorization is None or run is None or package is None or review is None or feedback is not None:
            _fail("state_payload_mismatch", "$", "accepted requires an exact owner review and no repair feedback")
        if review["decision"] != "accept":
            _fail("state_decision_mismatch", "$.owner_review.decision", "accepted state requires accept decision")
    elif state == "repair-requested":
        if authorization is None or run is None or package is None or review is None or feedback is None:
            _fail("state_payload_mismatch", "$", "repair-requested requires bound owner feedback")
        if review["decision"] != "request_repair":
            _fail(
                "state_decision_mismatch",
                "$.owner_review.decision",
                "repair-requested state requires request_repair decision",
            )
        if run["repair_attempts"] >= experiment["budget"]["max_repair_attempts"]:
            _fail(
                "repair_budget_exhausted",
                "$.run.repair_attempts",
                "owner cannot request another repair after the preregistered repair budget is exhausted",
            )
    else:
        if authorization is None or run is None or package is None or review is None or feedback is not None:
            _fail("state_payload_mismatch", "$", "rejected-stop requires an exact owner review and no repair feedback")
        if review["decision"] != "reject_stop":
            _fail(
                "state_decision_mismatch",
                "$.owner_review.decision",
                "rejected-stop state requires reject_stop decision",
            )

    return cast(OwnerReviewSessionV1, value)


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
    human_criteria: list[OwnerReviewCriterionV1],
    retention_prefix: str,
    budget: OwnerReviewBudgetV1,
) -> OwnerReviewSessionV1:
    """Preregister one experiment before any paid/provider execution begins."""

    experiment: OwnerReviewExperimentV1 = {
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
    session: OwnerReviewSessionV1 = {
        "schema": OWNER_REVIEW_SESSION_SCHEMA_V1,
        "state": "experiment-frozen",
        "experiment": experiment,
        "experiment_sha256": _canonical_digest(experiment),
        "owner_run_authorization": None,
        "run": None,
        "review_package": None,
        "owner_review": None,
        "feedback_intake": None,
        "authority": {
            "human": "repository-owner",
            "deterministic_qa": "retained-separate",
            "perceptual": "owner-human-only",
            "aesthetic_auto_accept": "forbidden",
        },
    }
    return validate_owner_review_session(session)


def authorize_owner_run(session: object, *, source_ref: str) -> OwnerReviewSessionV1:
    """Record explicit owner authorization before a bounded provider/external run may start."""

    current = validate_owner_review_session(session)
    if current["state"] != "experiment-frozen":
        _fail("invalid_transition", "$.state", "owner authorization requires experiment-frozen state")
    result = copy.deepcopy(current)
    result["state"] = "ready-for-owner-run"
    result["owner_run_authorization"] = {"source_ref": source_ref}
    return validate_owner_review_session(result)


def begin_owner_run(session: object) -> OwnerReviewSessionV1:
    """Enter running only after explicit owner authorization has been retained."""

    current = validate_owner_review_session(session)
    if current["state"] != "ready-for-owner-run":
        _fail("invalid_transition", "$.state", "run may begin only from ready-for-owner-run")
    result = copy.deepcopy(current)
    result["state"] = "running"
    return validate_owner_review_session(result)


def attach_owner_review_package(
    session: object,
    *,
    run: OwnerRunUsageV1,
    candidate_id: str,
    backend: str,
    candidate_rgba_sha256: str,
    native_png: OwnerReviewArtifactV1,
    preview_png: OwnerReviewArtifactV1,
    deterministic_qa_evidence: OwnerReviewArtifactV1,
    complexity_evidence: OwnerReviewArtifactV1,
) -> OwnerReviewSessionV1:
    """Freeze exact review evidence and enter the mandatory human-review stop state."""

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
    repair_feedback: list[OwnerRepairFeedbackInputV1] | None = None,
) -> OwnerReviewSessionV1:
    """Bind explicit owner judgment to the exact reviewed artifact without inventing missing detail."""

    current = validate_owner_review_session(session)
    if current["state"] != "awaiting-owner-review":
        _fail("invalid_transition", "$.state", "owner review requires awaiting-owner-review state")
    run = cast(OwnerRunUsageV1, current["run"])
    package = cast(OwnerReviewPackageV1, current["review_package"])
    experiment = current["experiment"]

    explicit = criterion_statuses or {}
    frozen_ids = [criterion["id"] for criterion in experiment["human_criteria"]]
    unknown = sorted(set(explicit) - set(frozen_ids))
    if unknown:
        _fail("unknown_criterion", "$.owner_review.criteria", f"unfrozen criteria supplied: {unknown}")
    for criterion_id, status in explicit.items():
        if status not in _CRITERION_STATUSES:
            _fail(
                "invalid_criterion_status",
                f"$.owner_review.criteria.{criterion_id}",
                "unsupported criterion status",
            )

    criteria: list[OwnerCriterionReviewV1] = [
        {"id": criterion_id, "status": explicit.get(criterion_id, "unresolved")}
        for criterion_id in frozen_ids
    ]

    result = copy.deepcopy(current)
    result["owner_review"] = {
        "source_ref": source_ref,
        "decision": decision,
        "summary": summary,
        "reviewed_run_id": run["run_id"],
        "reviewed_candidate_id": package["candidate_id"],
        "reviewed_native_png_sha256": package["native_png"]["sha256"],
        "criteria": criteria,
    }

    if decision == "accept":
        if repair_feedback:
            _fail("accepted_with_repair_feedback", "$.feedback_intake", "accept must not request repair")
        result["feedback_intake"] = None
        result["state"] = "accepted"
    elif decision == "reject_stop":
        if repair_feedback:
            _fail("rejected_stop_with_repair_feedback", "$.feedback_intake", "reject_stop must not request repair")
        result["feedback_intake"] = None
        result["state"] = "rejected-stop"
    elif decision == "request_repair":
        if not repair_feedback:
            _fail(
                "repair_feedback_required",
                "$.feedback_intake",
                "request_repair requires explicit owner feedback; do not invent repair targets",
            )
        if run["repair_attempts"] >= experiment["budget"]["max_repair_attempts"]:
            _fail(
                "repair_budget_exhausted",
                "$.run.repair_attempts",
                "preregistered repair budget is already exhausted",
            )
        items: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        for index, feedback in enumerate(repair_feedback):
            feedback_id = _require_text(feedback["id"], f"$.repair_feedback[{index}].id", maximum=64)
            if feedback_id in seen_ids:
                _fail("duplicate_feedback_id", f"$.repair_feedback[{index}].id", "feedback ids must be unique")
            seen_ids.add(feedback_id)
            feedback_summary = _require_text(
                feedback["summary"],
                f"$.repair_feedback[{index}].summary",
                maximum=512,
            )
            items.append(
                {
                    "id": feedback_id,
                    "authority": "owner_human",
                    "source_ref": source_ref,
                    "summary": feedback_summary,
                    "stage_hint": copy.deepcopy(feedback["stage_hint"]),
                    "region_hint": copy.deepcopy(feedback["region_hint"]),
                    "deterministic_qa": None,
                    "human": {"human_rejection": True, "scores": []},
                }
            )
        intake: FeedbackIntakeV1 = {
            "schema": FEEDBACK_INTAKE_SCHEMA_V1,
            "target": {
                "asset_id": experiment["asset_id"],
                "task_id": experiment["task_id"],
                "canvas": copy.deepcopy(experiment["canvas"]),
                "artifact_sha256": package["native_png"]["sha256"],
            },
            "items": cast(list, items),
        }
        result["feedback_intake"] = validate_feedback_intake(intake)
        result["state"] = "repair-requested"
    else:
        _fail("invalid_decision", "$.owner_review.decision", "unsupported owner review decision")

    return validate_owner_review_session(result)


__all__ = [
    "OWNER_REVIEW_SESSION_SCHEMA_V1",
    "MAX_OWNER_REVIEW_TEXT_CHARS_V1",
    "MAX_OWNER_REVIEW_ITEMS_V1",
    "OwnerReviewArtifactV1",
    "OwnerReviewBudgetV1",
    "OwnerReviewCriterionV1",
    "OwnerReviewDecisionRecordV1",
    "OwnerReviewDecisionV1",
    "OwnerReviewExperimentV1",
    "OwnerReviewPackageV1",
    "OwnerReviewSessionV1",
    "OwnerReviewStateV1",
    "OwnerReviewValidationError",
    "OwnerRepairFeedbackInputV1",
    "OwnerRunUsageV1",
    "authorize_owner_run",
    "begin_owner_run",
    "attach_owner_review_package",
    "freeze_owner_experiment",
    "record_owner_review",
    "validate_owner_review_session",
]
