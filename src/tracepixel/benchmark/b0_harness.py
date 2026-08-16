from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal, Mapping, TypedDict, cast

B0_PREREGISTRATION_SCHEMA_V1 = "tracepixel.b0-preregistration.v1"
B0_SCHEDULE_SCHEMA_V1 = "tracepixel.b0-schedule.v1"
B0_ATTEMPT_IDENTITY_SCHEMA_V1 = "tracepixel.b0-attempt-identity.v1"
B0_ATTEMPT_RESULT_SCHEMA_V1 = "tracepixel.b0-attempt-result.v1"
B0_VISIBLE_TASK_SCHEMA_V1 = "tracepixel.b0-visible-task.v1"
B0_FREEZE_COMMIT = "c4b31288867fd4c4cf5ea3664808bd6f47cca1db"

B0_REQUIRED_PAYLOAD_FILES = (
    "provider-request.json",
    "provider-response.json",
    "proposal-or-failure.json",
    "deterministic-qa.json",
    "telemetry.json",
)
B0_FAILURE_TAXONOMY = frozenset(
    (
        "budget_exhaustion",
        "timeout",
        "transport_provider_failure",
        "invalid_operation_or_ir",
        "deterministic_verifier_rejection",
        "semantic_visual_failure",
        "human_rejection",
        "void_infrastructure",
    )
)


class B0VisibleTaskV1(TypedDict):
    schema: Literal["tracepixel.b0-visible-task.v1"]
    task_id: str
    tier: str
    visible_text: str


class B0AttemptIdentityV1(TypedDict):
    schema: Literal["tracepixel.b0-attempt-identity.v1"]
    benchmark_id: Literal["B0"]
    freeze_commit: str
    repository_commit_under_test: str
    method_id: str
    task_id: str
    trial_index: int
    rerun_index: int
    rerun_of: str | None
    attempt_id: str


class B0ScheduleV1(TypedDict):
    schema: Literal["tracepixel.b0-schedule.v1"]
    benchmark_id: Literal["B0"]
    freeze_commit: str
    preregistration_sha256: str
    scheduled_attempt_count: int
    attempts: list[B0AttemptIdentityV1]


class B0StructuralScoreV1(TypedDict):
    applicable_rules: int
    passed_rules: int
    all_rules_pass: bool
    fraction_numerator: int
    fraction_denominator: int
    rule_results: dict[str, bool]


class B0InfrastructureVoidV1(TypedDict):
    reason: str
    fix_commit: str


class B0AttemptResultV1(TypedDict):
    schema: Literal["tracepixel.b0-attempt-result.v1"]
    identity: B0AttemptIdentityV1
    provider_invoked: bool
    completion: bool
    failure_category: str | None
    infrastructure_void: B0InfrastructureVoidV1 | None
    structural: B0StructuralScoreV1
    telemetry: dict[str, object] | None
    human_review: dict[str, object] | None
    artifacts: dict[str, dict[str, object]]
    notes: str | None


class B0HarnessContractError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise B0HarnessContractError(code, path, message)


def _dict(value: object, path: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    raw = cast(dict[object, object], value)
    if not all(type(key) is str for key in raw):
        _fail("invalid_fields", path, "object keys must be strings")
    return cast(dict[str, object], raw)


def _list(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def _text(value: object, path: str) -> str:
    if type(value) is not str or not cast(str, value):
        _fail("invalid_value", path, "must be a non-empty string")
    return cast(str, value)


def _positive_int(value: object, path: str) -> int:
    if type(value) is not int or cast(int, value) <= 0:
        _fail("invalid_value", path, "must be an integer > 0")
    return cast(int, value)


def _full_git_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value)


def _sha256_hex(value: object) -> bool:
    return (
        type(value) is str
        and len(cast(str, value)) == 64
        and all(character in "0123456789abcdef" for character in cast(str, value))
    )


def json_payload(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        + b"\n"
    )


def load_b0_preregistration(path: str | Path) -> tuple[dict[str, object], str]:
    source = Path(path).read_bytes()
    try:
        root = _dict(json.loads(source), "$preregistration")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("invalid_preregistration_json", "$preregistration", str(exc))
    if root.get("schema") != B0_PREREGISTRATION_SCHEMA_V1:
        _fail("unsupported_schema", "$preregistration.schema", B0_PREREGISTRATION_SCHEMA_V1)
    if root.get("benchmark_id") != "B0" or root.get("freeze_status") != "frozen":
        _fail("invalid_freeze", "$preregistration", "must be the frozen B0 cohort")
    _text(root.get("repository_commit_under_test"), "$preregistration.repository_commit_under_test")

    methods = _list(root.get("scored_methods"), "$preregistration.scored_methods")
    tasks = _list(root.get("tasks"), "$preregistration.tasks")
    if not methods or not tasks:
        _fail("empty_cohort", "$preregistration", "scored methods and tasks must be non-empty")
    method_ids = [_text(_dict(item, "$method").get("id"), "$method.id") for item in methods]
    task_ids = [_text(_dict(item, "$task").get("id"), "$task.id") for item in tasks]
    if len(set(method_ids)) != len(method_ids) or len(set(task_ids)) != len(task_ids):
        _fail("duplicate_identity", "$preregistration", "method/task IDs must be unique")
    for item in tasks:
        task = _dict(item, "$task")
        _text(task.get("tier"), "$task.tier")
        _text(task.get("visible_text"), "$task.visible_text")
        if not _dict(task.get("hidden_structural_constraints"), "$task.hidden_structural_constraints"):
            _fail("empty_constraints", "$task.hidden_structural_constraints", "must not be empty")

    budgets = _dict(root.get("budgets"), "$preregistration.budgets")
    _positive_int(
        budgets.get("trials_per_task_per_scored_method"),
        "$preregistration.budgets.trials_per_task_per_scored_method",
    )
    taxonomy = [_text(item, "$preregistration.failure_taxonomy[]") for item in _list(root.get("failure_taxonomy"), "$preregistration.failure_taxonomy")]
    if frozenset(taxonomy) != B0_FAILURE_TAXONOMY:
        _fail("failure_taxonomy_drift", "$preregistration.failure_taxonomy", "frozen taxonomy changed")

    retention = _dict(root.get("artifact_retention"), "$preregistration.artifact_retention")
    if retention.get("retain_every_scheduled_attempt") is not True:
        _fail("retention_disabled", "$preregistration.artifact_retention", "every attempt must be retained")
    required_files = _list(
        retention.get("required_files_per_attempt"),
        "$preregistration.artifact_retention.required_files_per_attempt",
    )
    for name in ("attempt-manifest.json", *B0_REQUIRED_PAYLOAD_FILES):
        if name not in required_files:
            _fail("retention_contract_drift", "$preregistration.artifact_retention", f"missing {name}")
    return root, sha256(source).hexdigest()


def _methods(preregistration: Mapping[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for item in _list(preregistration.get("scored_methods"), "$preregistration.scored_methods"):
        method = _dict(item, "$method")
        result[_text(method.get("id"), "$method.id")] = method
    return result


def _tasks(preregistration: Mapping[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for item in _list(preregistration.get("tasks"), "$preregistration.tasks"):
        task = _dict(item, "$task")
        result[_text(task.get("id"), "$task.id")] = task
    return result


def visible_task_packet(preregistration: Mapping[str, object], task_id: str) -> B0VisibleTaskV1:
    task = _tasks(preregistration).get(task_id)
    if task is None:
        _fail("unknown_task", "$task_id", task_id)
    return {
        "schema": B0_VISIBLE_TASK_SCHEMA_V1,
        "task_id": task_id,
        "tier": _text(task.get("tier"), "$task.tier"),
        "visible_text": _text(task.get("visible_text"), "$task.visible_text"),
    }


def _base_attempt_id(task_id: str, method_id: str, trial_index: int) -> str:
    return f"{task_id}__{method_id}__trial-{trial_index:02d}"


def _identity(
    repository_commit: str,
    method_id: str,
    task_id: str,
    trial_index: int,
    *,
    rerun_index: int = 0,
    rerun_of: str | None = None,
) -> B0AttemptIdentityV1:
    base = _base_attempt_id(task_id, method_id, trial_index)
    return {
        "schema": B0_ATTEMPT_IDENTITY_SCHEMA_V1,
        "benchmark_id": "B0",
        "freeze_commit": B0_FREEZE_COMMIT,
        "repository_commit_under_test": repository_commit,
        "method_id": method_id,
        "task_id": task_id,
        "trial_index": trial_index,
        "rerun_index": rerun_index,
        "rerun_of": rerun_of,
        "attempt_id": base if rerun_index == 0 else f"{base}__rerun-{rerun_index}",
    }


def build_b0_schedule(
    preregistration: Mapping[str, object],
    *,
    preregistration_sha256: str,
) -> B0ScheduleV1:
    if not _sha256_hex(preregistration_sha256):
        _fail("invalid_sha256", "$preregistration_sha256", "must be lowercase SHA-256 hex")
    repository_commit = _text(
        preregistration.get("repository_commit_under_test"),
        "$preregistration.repository_commit_under_test",
    )
    methods = list(_methods(preregistration))
    tasks = list(_tasks(preregistration))
    trials = _positive_int(
        _dict(preregistration.get("budgets"), "$preregistration.budgets").get("trials_per_task_per_scored_method"),
        "$preregistration.budgets.trials_per_task_per_scored_method",
    )
    attempts = [
        _identity(repository_commit, method_id, task_id, trial_index)
        for task_id in tasks
        for method_id in methods
        for trial_index in range(1, trials + 1)
    ]
    return {
        "schema": B0_SCHEDULE_SCHEMA_V1,
        "benchmark_id": "B0",
        "freeze_commit": B0_FREEZE_COMMIT,
        "preregistration_sha256": preregistration_sha256,
        "scheduled_attempt_count": len(attempts),
        "attempts": attempts,
    }


def validate_attempt_identity(
    identity: object,
    preregistration: Mapping[str, object],
) -> B0AttemptIdentityV1:
    root = _dict(identity, "$identity")
    required = frozenset(
        (
            "schema", "benchmark_id", "freeze_commit", "repository_commit_under_test",
            "method_id", "task_id", "trial_index", "rerun_index", "rerun_of", "attempt_id",
        )
    )
    if frozenset(root) != required:
        _fail("invalid_fields", "$identity", "identity fields must match v1 exactly")
    if root["schema"] != B0_ATTEMPT_IDENTITY_SCHEMA_V1 or root["benchmark_id"] != "B0":
        _fail("unsupported_schema", "$identity", "not a B0 attempt identity")
    if root["freeze_commit"] != B0_FREEZE_COMMIT:
        _fail("freeze_commit_mismatch", "$identity.freeze_commit", B0_FREEZE_COMMIT)
    repository_commit = _text(preregistration.get("repository_commit_under_test"), "$preregistration.repository_commit_under_test")
    if root["repository_commit_under_test"] != repository_commit:
        _fail("repository_commit_mismatch", "$identity.repository_commit_under_test", repository_commit)
    method_id = _text(root["method_id"], "$identity.method_id")
    task_id = _text(root["task_id"], "$identity.task_id")
    if method_id not in _methods(preregistration) or task_id not in _tasks(preregistration):
        _fail("unknown_attempt_member", "$identity", "method/task is not in frozen cohort")
    trial_index = _positive_int(root["trial_index"], "$identity.trial_index")
    max_trial = _positive_int(_dict(preregistration.get("budgets"), "$preregistration.budgets").get("trials_per_task_per_scored_method"), "$preregistration.budgets.trials_per_task_per_scored_method")
    if trial_index > max_trial:
        _fail("trial_out_of_range", "$identity.trial_index", f"must be <= {max_trial}")
    if type(root["rerun_index"]) is not int or cast(int, root["rerun_index"]) not in (0, 1):
        _fail("rerun_out_of_range", "$identity.rerun_index", "must be 0 or 1")
    rerun_index = cast(int, root["rerun_index"])
    base = _base_attempt_id(task_id, method_id, trial_index)
    if rerun_index == 0:
        if root["rerun_of"] is not None or root["attempt_id"] != base:
            _fail("invalid_primary_identity", "$identity", "primary identity drifted")
    elif root["rerun_of"] != base or root["attempt_id"] != f"{base}__rerun-1":
        _fail("invalid_rerun_identity", "$identity", "rerun must cite retained primary")
    return cast(B0AttemptIdentityV1, identity)


def applicable_structural_rules(
    preregistration: Mapping[str, object],
    task_id: str,
) -> tuple[str, ...]:
    task = _tasks(preregistration).get(task_id)
    if task is None:
        _fail("unknown_task", "$task_id", task_id)
    constraints = _dict(task.get("hidden_structural_constraints"), "$task.hidden_structural_constraints")
    return tuple(sorted(constraints))


def build_attempt_result(
    preregistration: Mapping[str, object],
    *,
    identity: B0AttemptIdentityV1,
    provider_invoked: bool,
    completion: bool,
    failure_category: str | None,
    rule_results: Mapping[str, bool] | None,
    telemetry: Mapping[str, object] | None = None,
    human_review: Mapping[str, object] | None = None,
    infrastructure_void: Mapping[str, object] | None = None,
    notes: str | None = None,
) -> B0AttemptResultV1:
    identity = validate_attempt_identity(identity, preregistration)
    if type(provider_invoked) is not bool or type(completion) is not bool:
        _fail("invalid_type", "$result", "provider_invoked/completion must be booleans")
    if failure_category is not None and failure_category not in B0_FAILURE_TAXONOMY:
        _fail("unknown_failure_category", "$result.failure_category", str(failure_category))
    if not completion and failure_category is None:
        _fail("missing_failure_category", "$result.failure_category", "non-completion must be classified")

    normalized_void: B0InfrastructureVoidV1 | None = None
    if failure_category == "void_infrastructure":
        if provider_invoked or completion or identity["rerun_index"] != 0:
            _fail("invalid_void", "$result", "void_infrastructure is pre-invocation and primary-only")
        if infrastructure_void is None:
            _fail("missing_void_record", "$result.infrastructure_void", "reason and fix_commit are required")
        record = _dict(dict(infrastructure_void), "$result.infrastructure_void")
        if frozenset(record) != frozenset(("reason", "fix_commit")):
            _fail("invalid_fields", "$result.infrastructure_void", "expected reason and fix_commit")
        reason = _text(record["reason"], "$result.infrastructure_void.reason")
        fix_commit = _text(record["fix_commit"], "$result.infrastructure_void.fix_commit")
        if not _full_git_sha(fix_commit):
            _fail("invalid_fix_commit", "$result.infrastructure_void.fix_commit", "must be full lowercase git SHA")
        normalized_void = {"reason": reason, "fix_commit": fix_commit}
    elif infrastructure_void is not None:
        _fail("unexpected_void_record", "$result.infrastructure_void", "only void_infrastructure may carry this record")

    rules = applicable_structural_rules(preregistration, identity["task_id"])
    if rule_results is None:
        normalized = {rule: False for rule in rules}
    else:
        normalized = dict(rule_results)
        if frozenset(normalized) != frozenset(rules) or not all(type(value) is bool for value in normalized.values()):
            _fail("structural_rule_set_mismatch", "$result.structural.rule_results", "score every frozen rule exactly once")
        normalized = {rule: normalized[rule] for rule in rules}
    passed = sum(normalized.values())
    denominator = len(rules)
    return {
        "schema": B0_ATTEMPT_RESULT_SCHEMA_V1,
        "identity": deepcopy(identity),
        "provider_invoked": provider_invoked,
        "completion": completion,
        "failure_category": failure_category,
        "infrastructure_void": normalized_void,
        "structural": {
            "applicable_rules": denominator,
            "passed_rules": passed,
            "all_rules_pass": passed == denominator,
            "fraction_numerator": passed,
            "fraction_denominator": denominator,
            "rule_results": normalized,
        },
        "telemetry": None if telemetry is None else dict(telemetry),
        "human_review": None if human_review is None else dict(human_review),
        "artifacts": {},
        "notes": notes,
    }


def make_void_infrastructure_rerun(
    primary_result: B0AttemptResultV1,
    preregistration: Mapping[str, object],
) -> B0AttemptIdentityV1:
    if primary_result.get("failure_category") != "void_infrastructure" or primary_result.get("infrastructure_void") is None:
        _fail("rerun_not_authorized", "$result", "only a retained void_infrastructure primary may rerun")
    primary = validate_attempt_identity(primary_result.get("identity"), preregistration)
    if primary["rerun_index"] != 0:
        _fail("rerun_out_of_range", "$identity.rerun_index", "cannot rerun a rerun")
    return _identity(
        primary["repository_commit_under_test"],
        primary["method_id"],
        primary["task_id"],
        primary["trial_index"],
        rerun_index=1,
        rerun_of=primary["attempt_id"],
    )


def blind_review_key(identity: B0AttemptIdentityV1) -> str:
    material = f"{identity['task_id']}|{identity['trial_index']}|{identity['method_id']}".encode("utf-8")
    return sha256(material).hexdigest()


def attempt_relative_path(identity: B0AttemptIdentityV1) -> Path:
    leaf = f"trial-{identity['trial_index']:02d}"
    if identity["rerun_index"]:
        leaf += f"-rerun-{identity['rerun_index']}"
    return Path(identity["freeze_commit"]) / identity["method_id"] / identity["task_id"] / leaf


def write_attempt_record(
    results_root: str | Path,
    preregistration: Mapping[str, object],
    result: B0AttemptResultV1,
    payloads: Mapping[str, bytes],
) -> Path:
    identity = validate_attempt_identity(result.get("identity"), preregistration)
    if result.get("schema") != B0_ATTEMPT_RESULT_SCHEMA_V1 or result.get("artifacts") != {}:
        _fail("invalid_result", "$result", "use build_attempt_result and leave artifact metadata to the writer")
    if result.get("structural") != build_attempt_result(
        preregistration,
        identity=identity,
        provider_invoked=cast(bool, result.get("provider_invoked")),
        completion=cast(bool, result.get("completion")),
        failure_category=cast(str | None, result.get("failure_category")),
        rule_results=cast(dict[str, bool], _dict(result.get("structural"), "$result.structural").get("rule_results")),
        telemetry=cast(dict[str, object] | None, result.get("telemetry")),
        human_review=cast(dict[str, object] | None, result.get("human_review")),
        infrastructure_void=cast(dict[str, object] | None, result.get("infrastructure_void")),
        notes=cast(str | None, result.get("notes")),
    )["structural"]:
        _fail("structural_score_mismatch", "$result.structural", "derived score was modified")

    for required in B0_REQUIRED_PAYLOAD_FILES:
        if required not in payloads:
            _fail("missing_required_artifact", "$payloads", required)
    if "attempt-manifest.json" in payloads:
        _fail("reserved_artifact", "$payloads", "attempt-manifest.json is generated by the harness")
    for name, payload in payloads.items():
        if type(name) is not str or not name or Path(name).name != name or name.startswith("."):
            _fail("invalid_artifact_name", "$payloads", repr(name))
        if type(payload) is not bytes:
            _fail("invalid_artifact_payload", f"$payloads.{name}", "must be bytes")

    target = Path(results_root) / attempt_relative_path(identity)
    target.mkdir(parents=True, exist_ok=False)
    try:
        for name, payload in payloads.items():
            (target / name).write_bytes(payload)
        manifest = deepcopy(result)
        manifest["artifacts"] = {
            name: {"sha256": sha256(payload).hexdigest(), "bytes": len(payload)}
            for name, payload in sorted(payloads.items())
        }
        (target / "attempt-manifest.json").write_bytes(json_payload(manifest))
    except Exception:
        # Keep the claimed attempt directory rather than making a failed write look as if it never happened.
        raise
    return target
