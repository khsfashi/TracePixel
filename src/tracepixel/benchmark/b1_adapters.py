from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Literal, Mapping, NotRequired, Sequence, TypedDict, cast

from tracepixel.model import (
    ArtIntentValidationError,
    PixelProgramValidationError,
    STAGE_SEQUENCE_V1,
    validate_art_intent,
    validate_pixel_program,
)

from .b1_harness import (
    B1_FREEZE_COMMIT,
    B1_SCORED_METHOD_IDS,
    attempt_relative_path,
    validate_b1_attempt_identity,
)

B1_METHOD_ADAPTER_SCHEMA_V1 = "tracepixel.b1-method-adapter.v1"
B1_PROVIDER_REQUEST_SCHEMA_V1 = "tracepixel.b1-provider-request.v1"
B1_VISIBLE_TASK_SCHEMA_V1 = "tracepixel.b1-visible-task.v1"
B1_DETERMINISTIC_FEEDBACK_SCHEMA_V1 = "tracepixel.b1-deterministic-feedback.v1"
B1_CODEX_EXEC_PLAN_SCHEMA_V1 = "tracepixel.b1-codex-exec-plan.v1"
B1_CODEX_CALL_SCHEMA_V1 = "tracepixel.b1-codex-call.v1"

B1_TRACEPIXEL_METHOD_ID = B1_SCORED_METHOD_IDS[0]
B1_RAW_METHOD_ID = B1_SCORED_METHOD_IDS[1]
B1_STAGE_SEQUENCE_V1 = STAGE_SEQUENCE_V1

_PROVIDER_FIELDS = (
    "provider_surface",
    "provider_auth_mode",
    "model",
    "reasoning_effort",
    "vision_input",
    "codex_cli_version",
    "sandbox",
    "ephemeral",
)
_EXPECTED_PROVIDER = {
    "provider_surface": "openai-codex-cli",
    "provider_auth_mode": "chatgpt",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "low",
    "vision_input": False,
    "codex_cli_version": "codex-cli 0.147.0",
    "sandbox": "read-only",
    "ephemeral": True,
}
_MATCHED_BUDGET_FIELDS = (
    "max_provider_calls_per_trial",
    "max_iterations_per_trial",
    "max_tool_calls_per_trial",
    "max_operations_per_trial",
    "max_pixel_edits_per_trial",
    "max_visual_observation_calls_per_trial",
    "max_reported_input_tokens_per_provider_call",
    "max_reported_output_tokens_per_provider_call",
    "provider_call_timeout_seconds",
    "trial_wall_timeout_seconds",
    "human_interventions_during_generation",
)
_TOOL_ITEM_TYPES = frozenset(
    (
        "command_execution",
        "mcp_tool_call",
        "web_search",
        "file_search",
        "image_generation",
    )
)


class B1VisibleTaskV1(TypedDict):
    schema: Literal["tracepixel.b1-visible-task.v1"]
    task_id: str
    tier: str
    visible_text: str


class B1DeterministicFeedbackV1(TypedDict):
    schema: Literal["tracepixel.b1-deterministic-feedback.v1"]
    available: bool
    findings: list[dict[str, object]]
    all_rules_pass: bool | None


class B1MethodAdapterV1(TypedDict):
    schema: Literal["tracepixel.b1-method-adapter.v1"]
    method_id: str
    family: str
    provider: dict[str, object]
    authoring_surface: dict[str, object]


class B1ProviderRequestV1(TypedDict):
    schema: Literal["tracepixel.b1-provider-request.v1"]
    attempt: dict[str, object]
    visible_task: B1VisibleTaskV1
    provider: dict[str, object]
    matched_budget: dict[str, object]
    authoring_surface: dict[str, object]
    deterministic_feedback: B1DeterministicFeedbackV1
    current_stage: NotRequired[str]
    method_context: NotRequired[dict[str, object]]


class B1CodexExecPlanV1(TypedDict):
    schema: Literal["tracepixel.b1-codex-exec-plan.v1"]
    version_check: list[str]
    expected_version: str
    auth_check: list[str]
    required_auth_marker: str
    forbid_api_key_auth: bool
    command: list[str]
    timeout_seconds: int
    output_schema: dict[str, object]
    prompt: str
    retention_relative_path: str


class B1AdapterContractError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise B1AdapterContractError(code, path, message)


def _dict(value: object, path: str) -> dict[str, object]:
    if type(value) is not dict or not all(type(key) is str for key in cast(dict[object, object], value)):
        _fail("invalid_type", path, "must be a JSON object with string keys")
    return cast(dict[str, object], value)


def _list(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def _text(value: object, path: str) -> str:
    if type(value) is not str or not cast(str, value):
        _fail("invalid_value", path, "must be a non-empty string")
    return cast(str, value)


def _validate_json(value: object, path: str) -> None:
    kind = type(value)
    if value is None or kind in (str, bool, int):
        if kind is str:
            normalized = cast(str, value).replace("\\", "/").lower()
            if "evidence/b0/results/" in normalized:
                _fail(
                    "b0_result_reference",
                    path,
                    "B1 provider-visible data must not read, seed from, or substitute a B0 scored result",
                )
        return
    if kind is float:
        if not isfinite(cast(float, value)):
            _fail("invalid_json_value", path, "JSON numbers must be finite")
        return
    if kind is list:
        for index, item in enumerate(cast(list[object], value)):
            _validate_json(item, f"{path}[{index}]")
        return
    if kind is dict:
        for key, item in cast(dict[object, object], value).items():
            if type(key) is not str:
                _fail("invalid_json_value", path, "object keys must be strings")
            if key == "hidden_structural_constraints":
                _fail("hidden_constraint_leak", path, "provider-visible payload exposed hidden constraints")
            _validate_json(item, f"{path}.{key}")
        return
    _fail("invalid_json_value", path, "must contain only JSON-compatible values")


def _methods(preregistration: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        _dict(item, "$preregistration.scored_methods[]")
        for item in _list(preregistration.get("scored_methods"), "$preregistration.scored_methods")
    ]


def validate_b1_scored_methods(
    preregistration: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    methods = _methods(preregistration)
    ids = tuple(_text(method.get("id"), "$method.id") for method in methods)
    if ids != B1_SCORED_METHOD_IDS:
        _fail(
            "scored_method_drift",
            "$preregistration.scored_methods",
            f"expected frozen order {B1_SCORED_METHOD_IDS!r}",
        )
    families = {
        B1_TRACEPIXEL_METHOD_ID: "tracepixel-staged-repair-agent",
        B1_RAW_METHOD_ID: "raw-primitive-agent",
    }
    for method in methods:
        method_id = cast(str, method["id"])
        if method.get("family") != families[method_id]:
            _fail("method_family_drift", "$method.family", method_id)
        if {field: method.get(field) for field in _PROVIDER_FIELDS} != _EXPECTED_PROVIDER:
            _fail(
                "provider_contract_drift",
                f"$method[{method_id}]",
                "frozen provider/model/auth settings changed",
            )
    return methods[0], methods[1]


def _surface(method_id: str) -> dict[str, object]:
    common: dict[str, object] = {
        "visible_task_schema": B1_VISIBLE_TASK_SCHEMA_V1,
        "pixel_program_schema": "tracepixel.pixel-program.v1",
        "operation_vocabulary": ["set_pixels"],
        "deterministic_feedback_schema": B1_DETERMINISTIC_FEEDBACK_SCHEMA_V1,
    }
    if method_id == B1_TRACEPIXEL_METHOD_ID:
        return {
            **common,
            "kind": "tracepixel-staged-repair-agent",
            "art_intent_schema": "tracepixel.art-intent.v1",
            "observation_schema": "tracepixel.agent-observation.v1",
            "proposal_envelope_schema": "tracepixel.agent-provider-proposal.v1",
            "stage_sequence": list(B1_STAGE_SEQUENCE_V1),
            "stage_guidance": True,
            "repair_surface": {
                "kind": "p7-bounded-deterministic-repair",
                "repair_evidence_schema": "tracepixel.repair-evidence.v1",
                "human_feedback_during_generation": False,
            },
        }
    if method_id == B1_RAW_METHOD_ID:
        return {**common, "kind": "raw-pixel-program"}
    _fail("unknown_method", "$method_id", method_id)


def build_b1_method_adapter(
    preregistration: Mapping[str, object],
    method_id: str,
) -> B1MethodAdapterV1:
    tracepixel, raw = validate_b1_scored_methods(preregistration)
    method = (
        tracepixel
        if method_id == B1_TRACEPIXEL_METHOD_ID
        else raw
        if method_id == B1_RAW_METHOD_ID
        else None
    )
    if method is None:
        _fail("unknown_method", "$method_id", method_id)
    adapter: B1MethodAdapterV1 = {
        "schema": B1_METHOD_ADAPTER_SCHEMA_V1,
        "method_id": method_id,
        "family": _text(method.get("family"), "$method.family"),
        "provider": {field: deepcopy(method[field]) for field in _PROVIDER_FIELDS},
        "authoring_surface": _surface(method_id),
    }
    _validate_json(adapter, "$adapter")
    return adapter


def b1_visible_task_packet(
    preregistration: Mapping[str, object],
    task_id: str,
) -> B1VisibleTaskV1:
    tasks = _list(preregistration.get("tasks"), "$preregistration.tasks")
    for item in tasks:
        task = _dict(item, "$task")
        if task.get("id") != task_id:
            continue
        packet: B1VisibleTaskV1 = {
            "schema": B1_VISIBLE_TASK_SCHEMA_V1,
            "task_id": _text(task.get("id"), "$task.id"),
            "tier": _text(task.get("tier"), "$task.tier"),
            "visible_text": _text(task.get("visible_text"), "$task.visible_text"),
        }
        _validate_json(packet, "$visible_task")
        return packet
    _fail("unknown_task", "$task_id", task_id)


def _art_intent_from_visible_task(task: B1VisibleTaskV1) -> dict[str, object]:
    text = task["visible_text"]
    lowered = text.lower()
    canvas = re.search(r"\b(\d+)x(\d+)\b", text)
    palette = re.search(r"at most (\d+) visible colors", text, flags=re.IGNORECASE)
    if canvas is None or palette is None:
        _fail(
            "visible_task_unparseable",
            "$visible_task.visible_text",
            "staged adapter requires explicit canvas and palette text",
        )

    symmetry: dict[str, object] | None = None
    if "symmetric horizontally and vertically" in lowered:
        symmetry = {"axis": "both", "strength": "required"}
    elif "vertically symmetric" in lowered:
        symmetry = {"axis": "vertical", "strength": "required"}
    elif "horizontally symmetric" in lowered:
        symmetry = {"axis": "horizontal", "strength": "required"}

    facing = (
        "front"
        if "front-facing" in lowered
        else "right"
        if "facing right" in lowered
        else "left"
        if "facing left" in lowered
        else None
    )
    intent = {
        "schema": "tracepixel.art-intent.v1",
        "asset_class": f"b1-benchmark-{task['task_id'].lower()}",
        "canvas": {"width": int(canvas.group(1)), "height": int(canvas.group(2))},
        "composition": {
            "occupied_bounds": None,
            "facing": facing,
            "symmetry": symmetry,
            "light_direction": None,
            "palette_budget": int(palette.group(1)),
        },
    }
    try:
        validate_art_intent(intent)
    except ArtIntentValidationError as exc:
        _fail(
            "invalid_visible_derived_art_intent",
            "$visible_task.visible_text",
            f"{exc.code}: {exc.message}",
        )
    return intent


def _matched_budget(preregistration: Mapping[str, object]) -> dict[str, object]:
    budgets = _dict(preregistration.get("budgets"), "$preregistration.budgets")
    if any(field not in budgets for field in _MATCHED_BUDGET_FIELDS):
        _fail("budget_contract_drift", "$preregistration.budgets", "missing frozen matched budget")
    return {field: deepcopy(budgets[field]) for field in _MATCHED_BUDGET_FIELDS}


def empty_b1_deterministic_feedback() -> B1DeterministicFeedbackV1:
    return {
        "schema": B1_DETERMINISTIC_FEEDBACK_SCHEMA_V1,
        "available": False,
        "findings": [],
        "all_rules_pass": None,
    }


def validate_b1_deterministic_feedback(feedback: object) -> B1DeterministicFeedbackV1:
    root = _dict(feedback, "$feedback")
    if frozenset(root) != frozenset(("schema", "available", "findings", "all_rules_pass")):
        _fail("invalid_fields", "$feedback", "feedback fields must match v1 exactly")
    if root["schema"] != B1_DETERMINISTIC_FEEDBACK_SCHEMA_V1 or type(root["available"]) is not bool:
        _fail("invalid_feedback", "$feedback", "schema/available field is invalid")
    findings = _list(root["findings"], "$feedback.findings")
    if root["available"] is False:
        if findings or root["all_rules_pass"] is not None:
            _fail(
                "unavailable_feedback_has_facts",
                "$feedback",
                "unavailable feedback must contain no QA facts",
            )
    elif type(root["all_rules_pass"]) is not bool:
        _fail(
            "invalid_feedback",
            "$feedback.all_rules_pass",
            "available feedback requires a boolean",
        )
    _validate_json(root, "$feedback")
    return cast(B1DeterministicFeedbackV1, feedback)


def build_b1_provider_request(
    preregistration: Mapping[str, object],
    *,
    identity: object,
    deterministic_feedback: B1DeterministicFeedbackV1 | None = None,
    current_stage: str | None = None,
) -> B1ProviderRequestV1:
    validated_identity = validate_b1_attempt_identity(identity, preregistration)
    method_id = cast(str, validated_identity["method_id"])
    adapter = build_b1_method_adapter(preregistration, method_id)
    visible_task = b1_visible_task_packet(
        preregistration,
        cast(str, validated_identity["task_id"]),
    )
    feedback = (
        empty_b1_deterministic_feedback()
        if deterministic_feedback is None
        else validate_b1_deterministic_feedback(deterministic_feedback)
    )

    if method_id == B1_TRACEPIXEL_METHOD_ID:
        current_stage = B1_STAGE_SEQUENCE_V1[0] if current_stage is None else current_stage
        if current_stage not in B1_STAGE_SEQUENCE_V1:
            _fail("invalid_stage", "$current_stage", str(current_stage))
    elif current_stage is not None:
        _fail(
            "raw_stage_guidance_forbidden",
            "$current_stage",
            "raw baseline may not receive a TracePixel stage",
        )

    request: B1ProviderRequestV1 = {
        "schema": B1_PROVIDER_REQUEST_SCHEMA_V1,
        "attempt": deepcopy(validated_identity),
        "visible_task": visible_task,
        "provider": deepcopy(adapter["provider"]),
        "matched_budget": _matched_budget(preregistration),
        "authoring_surface": deepcopy(adapter["authoring_surface"]),
        "deterministic_feedback": deepcopy(feedback),
    }
    if method_id == B1_TRACEPIXEL_METHOD_ID:
        assert current_stage is not None
        request["current_stage"] = current_stage
        request["method_context"] = {
            "art_intent": _art_intent_from_visible_task(visible_task),
            "observation_seed": {
                "schema": "tracepixel.b1-staged-observation-seed.v1",
                "current_stage": current_stage,
                "deterministic_feedback": deepcopy(feedback),
            },
            "repair_authority": deepcopy(adapter["authoring_surface"]["repair_surface"]),
        }
    _validate_json(request, "$request")
    return request


def _pixel_program_schema() -> dict[str, object]:
    pixel = {
        "type": "array",
        "items": {"type": "integer"},
        "minItems": 6,
        "maxItems": 6,
    }
    operation = {
        "type": "object",
        "additionalProperties": False,
        "required": ["op", "pixels"],
        "properties": {
            "op": {"type": "string", "const": "set_pixels"},
            "pixels": {"type": "array", "items": pixel},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema", "canvas", "operations"],
        "properties": {
            "schema": {"type": "string", "const": "tracepixel.pixel-program.v1"},
            "canvas": {
                "type": "object",
                "additionalProperties": False,
                "required": ["width", "height"],
                "properties": {
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                },
            },
            "operations": {"type": "array", "items": operation},
        },
    }


def b1_provider_output_schema(method_id: str) -> dict[str, object]:
    program = _pixel_program_schema()
    if method_id == B1_RAW_METHOD_ID:
        return program
    if method_id == B1_TRACEPIXEL_METHOD_ID:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema", "kind", "payload"],
            "properties": {
                "schema": {
                    "type": "string",
                    "const": "tracepixel.agent-provider-proposal.v1",
                },
                "kind": {"type": "string", "const": "pixel_program"},
                "payload": program,
            },
        }
    _fail("unknown_method", "$method_id", method_id)


def normalize_b1_provider_output(method_id: str, output: object) -> dict[str, object]:
    root = _dict(output, "$provider_output")
    if method_id == B1_TRACEPIXEL_METHOD_ID:
        if (
            frozenset(root) != frozenset(("schema", "kind", "payload"))
            or root.get("schema") != "tracepixel.agent-provider-proposal.v1"
            or root.get("kind") != "pixel_program"
        ):
            _fail(
                "invalid_tracepixel_output",
                "$provider_output",
                "expected the pixel_program Agent proposal envelope",
            )
        program = _dict(root["payload"], "$provider_output.payload")
    elif method_id == B1_RAW_METHOD_ID:
        program = root
    else:
        _fail("unknown_method", "$method_id", method_id)
    try:
        validate_pixel_program(program)
    except PixelProgramValidationError as exc:
        _fail(
            "invalid_pixel_program",
            "$provider_output",
            f"{exc.code}: {exc.message}",
        )
    _validate_json(program, "$provider_output")
    return deepcopy(program)


def render_b1_codex_prompt(request: B1ProviderRequestV1) -> str:
    if request.get("schema") != B1_PROVIDER_REQUEST_SCHEMA_V1:
        _fail("unsupported_schema", "$request.schema", B1_PROVIDER_REQUEST_SCHEMA_V1)
    _validate_json(request, "$request")
    method_id = _text(
        _dict(request.get("attempt"), "$request.attempt").get("method_id"),
        "$request.attempt.method_id",
    )
    if method_id == B1_TRACEPIXEL_METHOD_ID:
        prefix = (
            "Act only as the frozen TracePixel post-P7 B1 authoring adapter. "
            "Use the visible task, current TracePixel stage, staged/repair authoring surface, "
            "and deterministic feedback in the request. Do not inspect the filesystem, run shell commands, "
            "use vision, read prior benchmark outputs, or add hidden task assumptions. "
            "Return exactly one tracepixel.agent-provider-proposal.v1 pixel_program envelope using only set_pixels."
        )
    elif method_id == B1_RAW_METHOD_ID:
        prefix = (
            "Act only as the frozen raw PixelProgram B1 baseline. "
            "Use the visible task and deterministic feedback in the request. "
            "Do not inspect the filesystem, run shell commands, use vision, read prior benchmark outputs, "
            "or add hidden task assumptions. Return exactly one tracepixel.pixel-program.v1 using only set_pixels."
        )
    else:
        _fail("unknown_method", "$request.attempt.method_id", method_id)
    payload = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}\nB1_REQUEST={payload}"


def build_b1_codex_exec_plan(request: B1ProviderRequestV1) -> B1CodexExecPlanV1:
    provider = _dict(request.get("provider"), "$request.provider")
    if {field: provider.get(field) for field in _PROVIDER_FIELDS} != _EXPECTED_PROVIDER:
        _fail(
            "provider_contract_drift",
            "$request.provider",
            "request provider settings do not match B1-F0",
        )
    budget = _dict(request.get("matched_budget"), "$request.matched_budget")
    timeout = budget.get("provider_call_timeout_seconds")
    if type(timeout) is not int or cast(int, timeout) <= 0:
        _fail(
            "invalid_timeout",
            "$request.matched_budget.provider_call_timeout_seconds",
            "must be positive",
        )
    identity = _dict(request.get("attempt"), "$request.attempt")
    method_id = _text(identity.get("method_id"), "$request.attempt.method_id")
    retention_relative_path = (
        Path("evidence")
        / "b1"
        / "results"
        / attempt_relative_path(identity)
    ).as_posix()
    if not retention_relative_path.startswith(f"evidence/b1/results/{B1_FREEZE_COMMIT}/"):
        _fail(
            "invalid_retention_path",
            "$request.attempt",
            "B1 attempt retention escaped the exact frozen B1 result root",
        )
    _validate_json(retention_relative_path, "$retention_relative_path")
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--json",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--model",
        cast(str, provider["model"]),
        "--config",
        f"model_reasoning_effort={provider['reasoning_effort']}",
        "--output-schema",
        "<B1_OUTPUT_SCHEMA_PATH>",
        "--output-last-message",
        "<B1_OUTPUT_PATH>",
        "-",
    ]
    return {
        "schema": B1_CODEX_EXEC_PLAN_SCHEMA_V1,
        "version_check": ["codex", "--version"],
        "expected_version": cast(str, provider["codex_cli_version"]),
        "auth_check": ["codex", "login", "status"],
        "required_auth_marker": "Logged in using ChatGPT",
        "forbid_api_key_auth": True,
        "command": command,
        "timeout_seconds": cast(int, timeout),
        "output_schema": b1_provider_output_schema(method_id),
        "prompt": render_b1_codex_prompt(request),
        "retention_relative_path": retention_relative_path,
    }


@dataclass(frozen=True, slots=True)
class B1CodexCall:
    status: str
    output: object | None
    raw_output: str | None
    input_tokens: int | None
    output_tokens: int | None
    tool_calls: int | None
    wall_time_ms: int
    returncode: int | None
    error_code: str | None

    def record(self, call_index: int) -> dict[str, object]:
        return {
            "schema": B1_CODEX_CALL_SCHEMA_V1,
            "call_index": call_index,
            "status": self.status,
            "returncode": self.returncode,
            "error_code": self.error_code,
            "raw_output": self.raw_output,
            "raw_output_sha256": None if self.raw_output is None else sha256(self.raw_output.encode("utf-8")).hexdigest(),
            "output": deepcopy(self.output),
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
            },
            "tool_calls": self.tool_calls,
            "wall_time_ms": self.wall_time_ms,
        }


_Run = Callable[..., subprocess.CompletedProcess[str]]
_Which = Callable[[str], str | None]


class B1CodexExecutor:
    """Exact owner-local Codex executor for the provider boundary frozen by B1-F0."""

    def __init__(
        self,
        *,
        executable: str = "codex",
        _run: _Run = subprocess.run,
        _which: _Which = shutil.which,
    ) -> None:
        self._executable_name = executable
        self._run = _run
        self._which = _which
        self._resolved: str | None = None
        self._environment: dict[str, object] | None = None

    def _resolve(self) -> str:
        if self._resolved is not None:
            return self._resolved
        resolved = self._which(self._executable_name)
        if resolved is None:
            _fail("codex_not_found", "$executor", f"cannot find {self._executable_name!r} on PATH")
        self._resolved = resolved
        return resolved

    @staticmethod
    def _command(executable: str, arguments: Sequence[str]) -> list[str]:
        if Path(executable).suffix.lower() in (".cmd", ".bat"):
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            return [
                comspec,
                "/d",
                "/s",
                "/c",
                subprocess.list2cmdline([executable, *arguments]),
            ]
        return [executable, *arguments]

    def _metadata(self, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        executable = self._resolve()
        try:
            result = self._run(
                self._command(executable, arguments),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            _fail("codex_preflight_failed", "$executor", str(exc))
        if result.returncode != 0:
            _fail(
                "codex_preflight_failed",
                "$executor",
                f"Codex metadata command exited with {result.returncode}",
            )
        return result

    def preflight(self, request: B1ProviderRequestV1) -> dict[str, object]:
        plan = build_b1_codex_exec_plan(request)
        version_result = self._metadata(plan["version_check"][1:])
        version = (version_result.stdout or version_result.stderr).strip()
        if version != plan["expected_version"]:
            _fail(
                "codex_version_mismatch",
                "$executor.version",
                f"expected {plan['expected_version']!r}, got {version!r}",
            )
        auth_result = self._metadata(plan["auth_check"][1:])
        auth_text = "\n".join(
            part.strip()
            for part in (auth_result.stdout, auth_result.stderr)
            if part.strip()
        )
        if plan["required_auth_marker"] not in auth_text:
            _fail(
                "chatgpt_login_required",
                "$executor.auth",
                f"Codex must report {plan['required_auth_marker']!r}",
            )
        if plan["forbid_api_key_auth"] and "Logged in using an API key" in auth_text:
            _fail(
                "api_key_auth_forbidden",
                "$executor.auth",
                "B1 forbids API-key authenticated provider execution",
            )
        self._environment = {
            "provider_surface": "openai-codex-cli",
            "auth_mode": "chatgpt",
            "codex_cli_version": version,
            "model": request["provider"]["model"],
            "reasoning_effort": request["provider"]["reasoning_effort"],
            "sandbox": request["provider"]["sandbox"],
            "ephemeral": request["provider"]["ephemeral"],
            "vision_input": request["provider"]["vision_input"],
        }
        return deepcopy(self._environment)

    @staticmethod
    def _usage(stdout: str) -> tuple[int | None, int | None]:
        last: tuple[int | None, int | None] = (None, None)
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if type(event) is not dict or event.get("type") != "turn.completed":
                continue
            usage = event.get("usage")
            if type(usage) is not dict:
                continue
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            last = (
                input_tokens if type(input_tokens) is int and input_tokens >= 0 else None,
                output_tokens if type(output_tokens) is int and output_tokens >= 0 else None,
            )
        return last

    @staticmethod
    def _tool_calls(stdout: str) -> int:
        count = 0
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if type(event) is not dict or event.get("type") != "item.completed":
                continue
            item = event.get("item")
            if (
                type(item) is dict
                and cast(dict[str, object], item).get("type") in _TOOL_ITEM_TYPES
            ):
                count += 1
        return count

    def invoke(self, request: B1ProviderRequestV1, *, call_index: int) -> B1CodexCall:
        if type(call_index) is not int or call_index <= 0:
            _fail("invalid_call_index", "$call_index", "must be an integer > 0")
        plan = build_b1_codex_exec_plan(request)
        executable = self._resolve()
        with tempfile.TemporaryDirectory(prefix="tracepixel-b1-") as temporary:
            directory = Path(temporary)
            schema_path = directory / "output.schema.json"
            output_path = directory / "output.json"
            schema_path.write_text(
                json.dumps(
                    plan["output_schema"],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            arguments = list(plan["command"][1:])
            arguments[arguments.index("<B1_OUTPUT_SCHEMA_PATH>")] = str(schema_path)
            arguments[arguments.index("<B1_OUTPUT_PATH>")] = str(output_path)
            started = time.monotonic()
            try:
                result = self._run(
                    self._command(executable, arguments),
                    input=plan["prompt"],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=plan["timeout_seconds"],
                    check=False,
                )
            except subprocess.TimeoutExpired:
                elapsed = int((time.monotonic() - started) * 1000)
                return B1CodexCall(
                    "timeout",
                    None,
                    None,
                    None,
                    None,
                    None,
                    elapsed,
                    None,
                    "codex_timeout",
                )
            except OSError:
                elapsed = int((time.monotonic() - started) * 1000)
                return B1CodexCall(
                    "transport_failure",
                    None,
                    None,
                    None,
                    None,
                    None,
                    elapsed,
                    None,
                    "codex_launch_failed",
                )

            elapsed = int((time.monotonic() - started) * 1000)
            stdout = result.stdout or ""
            input_tokens, output_tokens = self._usage(stdout)
            tool_calls = self._tool_calls(stdout)
            try:
                raw_output = output_path.read_text(encoding="utf-8")
            except OSError:
                raw_output = None
            if raw_output is None or not raw_output.strip():
                code = "codex_exec_failed" if result.returncode else "codex_output_missing"
                return B1CodexCall(
                    "transport_failure",
                    None,
                    None,
                    input_tokens,
                    output_tokens,
                    tool_calls,
                    elapsed,
                    result.returncode,
                    code,
                )
            try:
                output: object | None = json.loads(raw_output)
            except json.JSONDecodeError:
                output = None
            return B1CodexCall(
                "response",
                output,
                raw_output,
                input_tokens,
                output_tokens,
                tool_calls,
                elapsed,
                result.returncode,
                None,
            )
