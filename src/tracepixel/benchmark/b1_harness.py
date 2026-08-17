from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping, cast

B1_PREREGISTRATION_SCHEMA_V1 = "tracepixel.b1-preregistration.v1"
B1_FREEZE_RECORD_SCHEMA_V1 = "tracepixel.b1-freeze-record.v1"
B1_SCHEDULE_SCHEMA_V1 = "tracepixel.b1-schedule.v1"
B1_ATTEMPT_IDENTITY_SCHEMA_V1 = "tracepixel.b1-attempt-identity.v1"

B1_FREEZE_COMMIT = "ca612a026ff5e74c397d9aa4ef8c0bdb25d1df6a"
B1_REPOSITORY_COMMIT_UNDER_TEST = "0ee45b1e466d4d1ec4e077b835ae31d47a1379a1"
B1_SCORED_METHOD_IDS = ("tracepixel-post-p7-v1", "raw-pixel-program-v1")
B1_EXPECTED_ATTEMPTS = 28

B1_FAILURE_TAXONOMY = frozenset(
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


class B1HarnessContractError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise B1HarnessContractError(code, path, message)


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


def _sha256_hex(value: object) -> bool:
    return (
        type(value) is str
        and len(cast(str, value)) == 64
        and all(character in "0123456789abcdef" for character in cast(str, value))
    )


def _read_json(path: str | Path, label: str) -> tuple[dict[str, object], bytes]:
    source_path = Path(path)
    try:
        source = source_path.read_bytes()
        decoded = json.loads(source)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("invalid_json", label, str(exc))
    return _dict(decoded, label), source


def load_b1_preregistration(path: str | Path) -> tuple[dict[str, object], str]:
    root, source = _read_json(path, "$preregistration")
    if root.get("schema") != B1_PREREGISTRATION_SCHEMA_V1:
        _fail("unsupported_schema", "$preregistration.schema", B1_PREREGISTRATION_SCHEMA_V1)
    if root.get("benchmark_id") != "B1" or root.get("freeze_status") != "frozen":
        _fail("invalid_freeze", "$preregistration", "must be the frozen B1 cohort")
    if root.get("repository_commit_under_test") != B1_REPOSITORY_COMMIT_UNDER_TEST:
        _fail(
            "repository_commit_drift",
            "$preregistration.repository_commit_under_test",
            B1_REPOSITORY_COMMIT_UNDER_TEST,
        )

    methods = [_dict(item, "$method") for item in _list(root.get("scored_methods"), "$preregistration.scored_methods")]
    method_ids = tuple(_text(method.get("id"), "$method.id") for method in methods)
    if method_ids != B1_SCORED_METHOD_IDS:
        _fail("scored_method_drift", "$preregistration.scored_methods", repr(B1_SCORED_METHOD_IDS))

    tasks = [_dict(item, "$task") for item in _list(root.get("tasks"), "$preregistration.tasks")]
    if len(tasks) != 7:
        _fail("task_count_drift", "$preregistration.tasks", "B1-v1 requires exactly seven held-out tasks")
    ids = [_text(task.get("id"), "$task.id") for task in tasks]
    texts = [_text(task.get("visible_text"), "$task.visible_text") for task in tasks]
    if len(set(ids)) != len(ids) or len(set(texts)) != len(texts):
        _fail("duplicate_task", "$preregistration.tasks", "task IDs and visible text must be unique")
    for task in tasks:
        _text(task.get("tier"), "$task.tier")
        if not _dict(task.get("hidden_structural_constraints"), "$task.hidden_structural_constraints"):
            _fail("empty_constraints", "$task.hidden_structural_constraints", "must not be empty")

    budgets = _dict(root.get("budgets"), "$preregistration.budgets")
    if _positive_int(
        budgets.get("trials_per_task_per_scored_method"),
        "$preregistration.budgets.trials_per_task_per_scored_method",
    ) != 2:
        _fail("trial_count_drift", "$preregistration.budgets", "B1-v1 freezes two trials per task/method")
    if budgets.get("human_interventions_during_generation") != 0:
        _fail("human_intervention_drift", "$preregistration.budgets", "generation-time human intervention must remain zero")

    taxonomy = frozenset(
        _text(item, "$preregistration.failure_taxonomy[]")
        for item in _list(root.get("failure_taxonomy"), "$preregistration.failure_taxonomy")
    )
    if taxonomy != B1_FAILURE_TAXONOMY:
        _fail("failure_taxonomy_drift", "$preregistration.failure_taxonomy", "frozen taxonomy changed")

    retention = _dict(root.get("artifact_retention"), "$preregistration.artifact_retention")
    if retention.get("retain_every_scheduled_attempt") is not True:
        _fail("retention_disabled", "$preregistration.artifact_retention", "every scheduled attempt must be retained")
    separation = _text(retention.get("b0_separation"), "$preregistration.artifact_retention.b0_separation")
    if "No retained B1 attempt file" not in separation:
        _fail("b0_separation_drift", "$preregistration.artifact_retention", "explicit B0 separation is required")
    return root, sha256(source).hexdigest()


def load_b1_freeze_record(path: str | Path) -> dict[str, object]:
    root, _ = _read_json(path, "$freeze")
    required = frozenset(
        (
            "schema",
            "benchmark_id",
            "freeze_commit",
            "preregistration_path",
            "repository_commit_under_test",
            "source_pr",
            "scoring_authority",
            "b0_boundary",
        )
    )
    if frozenset(root) != required:
        _fail("invalid_fields", "$freeze", "freeze record fields must match v1 exactly")
    if root.get("schema") != B1_FREEZE_RECORD_SCHEMA_V1 or root.get("benchmark_id") != "B1":
        _fail("unsupported_schema", "$freeze", "not a B1 freeze record")
    if root.get("freeze_commit") != B1_FREEZE_COMMIT:
        _fail("freeze_commit_mismatch", "$freeze.freeze_commit", B1_FREEZE_COMMIT)
    if root.get("repository_commit_under_test") != B1_REPOSITORY_COMMIT_UNDER_TEST:
        _fail("repository_commit_mismatch", "$freeze.repository_commit_under_test", B1_REPOSITORY_COMMIT_UNDER_TEST)
    if root.get("preregistration_path") != "evidence/b1/preregistration.v1.json":
        _fail("preregistration_path_drift", "$freeze.preregistration_path", "unexpected path")
    if root.get("source_pr") != 81:
        _fail("source_pr_drift", "$freeze.source_pr", "B1-F0 froze through PR #81")
    _text(root.get("scoring_authority"), "$freeze.scoring_authority")
    _text(root.get("b0_boundary"), "$freeze.b0_boundary")
    return root


def assert_b1_is_held_out(
    b1_preregistration: Mapping[str, object],
    b0_preregistration: Mapping[str, object],
) -> None:
    b1_tasks = [_dict(item, "$b1.tasks[]") for item in _list(b1_preregistration.get("tasks"), "$b1.tasks")]
    b0_tasks = [_dict(item, "$b0.tasks[]") for item in _list(b0_preregistration.get("tasks"), "$b0.tasks")]
    b1_ids = {_text(task.get("id"), "$b1.task.id") for task in b1_tasks}
    b0_ids = {_text(task.get("id"), "$b0.task.id") for task in b0_tasks}
    b1_texts = {_text(task.get("visible_text"), "$b1.task.visible_text") for task in b1_tasks}
    b0_texts = {_text(task.get("visible_text"), "$b0.task.visible_text") for task in b0_tasks}
    if not b1_ids.isdisjoint(b0_ids):
        _fail("b0_task_reuse", "$b1.tasks", "B1 task IDs overlap frozen B0")
    if not b1_texts.isdisjoint(b0_texts):
        _fail("b0_text_reuse", "$b1.tasks", "B1 visible task text overlaps frozen B0")


def _attempt_id(task_id: str, method_id: str, trial_index: int) -> str:
    return f"{task_id}__{method_id}__trial-{trial_index:02d}"


def build_b1_schedule(
    preregistration: Mapping[str, object],
    *,
    preregistration_sha256: str,
) -> dict[str, object]:
    if not _sha256_hex(preregistration_sha256):
        _fail("invalid_sha256", "$preregistration_sha256", "must be lowercase SHA-256 hex")
    if preregistration.get("repository_commit_under_test") != B1_REPOSITORY_COMMIT_UNDER_TEST:
        _fail("repository_commit_drift", "$preregistration", B1_REPOSITORY_COMMIT_UNDER_TEST)

    methods = [
        _text(_dict(item, "$method").get("id"), "$method.id")
        for item in _list(preregistration.get("scored_methods"), "$preregistration.scored_methods")
    ]
    if tuple(methods) != B1_SCORED_METHOD_IDS:
        _fail("scored_method_drift", "$preregistration.scored_methods", repr(B1_SCORED_METHOD_IDS))
    tasks = [
        _text(_dict(item, "$task").get("id"), "$task.id")
        for item in _list(preregistration.get("tasks"), "$preregistration.tasks")
    ]
    trials = _positive_int(
        _dict(preregistration.get("budgets"), "$preregistration.budgets").get("trials_per_task_per_scored_method"),
        "$preregistration.budgets.trials_per_task_per_scored_method",
    )

    attempts: list[dict[str, object]] = []
    for task_id in tasks:
        for method_id in methods:
            for trial_index in range(1, trials + 1):
                attempts.append(
                    {
                        "schema": B1_ATTEMPT_IDENTITY_SCHEMA_V1,
                        "benchmark_id": "B1",
                        "freeze_commit": B1_FREEZE_COMMIT,
                        "repository_commit_under_test": B1_REPOSITORY_COMMIT_UNDER_TEST,
                        "method_id": method_id,
                        "task_id": task_id,
                        "trial_index": trial_index,
                        "attempt_id": _attempt_id(task_id, method_id, trial_index),
                    }
                )
    if len(attempts) != B1_EXPECTED_ATTEMPTS:
        _fail("schedule_count_drift", "$schedule", f"expected {B1_EXPECTED_ATTEMPTS} attempts")
    return {
        "schema": B1_SCHEDULE_SCHEMA_V1,
        "benchmark_id": "B1",
        "freeze_commit": B1_FREEZE_COMMIT,
        "preregistration_sha256": preregistration_sha256,
        "scheduled_attempt_count": len(attempts),
        "attempts": attempts,
    }


def validate_b1_attempt_identity(identity: object, preregistration: Mapping[str, object]) -> dict[str, object]:
    root = _dict(identity, "$identity")
    required = frozenset(
        (
            "schema",
            "benchmark_id",
            "freeze_commit",
            "repository_commit_under_test",
            "method_id",
            "task_id",
            "trial_index",
            "attempt_id",
        )
    )
    if frozenset(root) != required:
        _fail("invalid_fields", "$identity", "attempt identity fields must match v1 exactly")
    if root.get("schema") != B1_ATTEMPT_IDENTITY_SCHEMA_V1 or root.get("benchmark_id") != "B1":
        _fail("unsupported_schema", "$identity", "not a B1 attempt identity")
    if root.get("freeze_commit") != B1_FREEZE_COMMIT:
        _fail("freeze_commit_mismatch", "$identity.freeze_commit", B1_FREEZE_COMMIT)
    if root.get("repository_commit_under_test") != B1_REPOSITORY_COMMIT_UNDER_TEST:
        _fail("repository_commit_mismatch", "$identity.repository_commit_under_test", B1_REPOSITORY_COMMIT_UNDER_TEST)

    method_id = _text(root.get("method_id"), "$identity.method_id")
    task_id = _text(root.get("task_id"), "$identity.task_id")
    trial_index = _positive_int(root.get("trial_index"), "$identity.trial_index")
    methods = {
        _text(_dict(item, "$method").get("id"), "$method.id")
        for item in _list(preregistration.get("scored_methods"), "$preregistration.scored_methods")
    }
    tasks = {
        _text(_dict(item, "$task").get("id"), "$task.id")
        for item in _list(preregistration.get("tasks"), "$preregistration.tasks")
    }
    if method_id not in methods or task_id not in tasks:
        _fail("unknown_attempt_member", "$identity", "method/task is not in frozen B1")
    if trial_index not in (1, 2):
        _fail("trial_out_of_range", "$identity.trial_index", "B1-v1 trials are 1 or 2")
    if root.get("attempt_id") != _attempt_id(task_id, method_id, trial_index):
        _fail("attempt_id_drift", "$identity.attempt_id", "attempt ID does not match frozen identity")
    return deepcopy(root)


def attempt_relative_path(identity: object) -> Path:
    root = _dict(identity, "$identity")
    method_id = _text(root.get("method_id"), "$identity.method_id")
    task_id = _text(root.get("task_id"), "$identity.task_id")
    trial_index = _positive_int(root.get("trial_index"), "$identity.trial_index")
    for value, label in ((method_id, "method_id"), (task_id, "task_id")):
        if "/" in value or "\\" in value or value in (".", ".."):
            _fail("unsafe_path_component", f"$identity.{label}", value)
    return Path(B1_FREEZE_COMMIT) / method_id / task_id / f"trial-{trial_index:02d}"
