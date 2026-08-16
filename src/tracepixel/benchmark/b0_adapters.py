from __future__ import annotations

from copy import deepcopy
import json
from math import isfinite
import re
from typing import Literal, Mapping, NotRequired, TypedDict, cast

from tracepixel.model import (
    ArtIntentValidationError,
    PixelProgramValidationError,
    STAGE_SEQUENCE_V1,
    validate_art_intent,
    validate_pixel_program,
)

from .b0_harness import B0AttemptIdentityV1, B0VisibleTaskV1, validate_attempt_identity, visible_task_packet

B0_METHOD_ADAPTER_SCHEMA_V1 = "tracepixel.b0-method-adapter.v1"
B0_PROVIDER_REQUEST_SCHEMA_V1 = "tracepixel.b0-provider-request.v1"
B0_DETERMINISTIC_FEEDBACK_SCHEMA_V1 = "tracepixel.b0-deterministic-feedback.v1"
B0_CODEX_EXEC_PLAN_SCHEMA_V1 = "tracepixel.b0-codex-exec-plan.v1"

B0_TRACEPIXEL_METHOD_ID = "tracepixel-staged-v1"
B0_RAW_METHOD_ID = "raw-pixel-program-v1"
B0_SCORED_METHOD_IDS = (B0_TRACEPIXEL_METHOD_ID, B0_RAW_METHOD_ID)
B0_STAGE_SEQUENCE_V1 = STAGE_SEQUENCE_V1

_PROVIDER_FIELDS = (
    "provider_surface", "provider_auth_mode", "model", "reasoning_effort",
    "vision_input", "codex_cli_version", "sandbox", "ephemeral",
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
    "max_provider_calls_per_trial", "max_iterations_per_trial", "max_tool_calls_per_trial",
    "max_operations_per_trial", "max_pixel_edits_per_trial",
    "max_visual_observation_calls_per_trial", "max_reported_input_tokens_per_provider_call",
    "max_reported_output_tokens_per_provider_call", "provider_call_timeout_seconds",
    "trial_wall_timeout_seconds", "human_interventions_during_generation",
)


class B0DeterministicFeedbackV1(TypedDict):
    schema: Literal["tracepixel.b0-deterministic-feedback.v1"]
    available: bool
    findings: list[dict[str, object]]
    all_rules_pass: bool | None


class B0MethodAdapterV1(TypedDict):
    schema: Literal["tracepixel.b0-method-adapter.v1"]
    method_id: str
    family: str
    provider: dict[str, object]
    authoring_surface: dict[str, object]


class B0ProviderRequestV1(TypedDict):
    schema: Literal["tracepixel.b0-provider-request.v1"]
    attempt: dict[str, object]
    visible_task: B0VisibleTaskV1
    provider: dict[str, object]
    matched_budget: dict[str, object]
    authoring_surface: dict[str, object]
    deterministic_feedback: B0DeterministicFeedbackV1
    current_stage: NotRequired[str]
    method_context: NotRequired[dict[str, object]]


class B0CodexExecPlanV1(TypedDict):
    schema: Literal["tracepixel.b0-codex-exec-plan.v1"]
    version_check: list[str]
    expected_version: str
    auth_check: list[str]
    required_auth_marker: str
    forbid_api_key_auth: bool
    command: list[str]
    timeout_seconds: int
    output_schema: dict[str, object]
    prompt: str


class B0AdapterContractError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code, self.path, self.message = code, path, message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise B0AdapterContractError(code, path, message)


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
    return [_dict(item, "$preregistration.scored_methods[]") for item in _list(preregistration.get("scored_methods"), "$preregistration.scored_methods")]


def validate_b0_scored_methods(preregistration: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    methods = _methods(preregistration)
    ids = tuple(_text(method.get("id"), "$method.id") for method in methods)
    if ids != B0_SCORED_METHOD_IDS:
        _fail("scored_method_drift", "$preregistration.scored_methods", f"expected frozen order {B0_SCORED_METHOD_IDS!r}")
    families = {B0_TRACEPIXEL_METHOD_ID: "tracepixel-staged-agent", B0_RAW_METHOD_ID: "raw-primitive-agent"}
    for method in methods:
        method_id = cast(str, method["id"])
        if method.get("family") != families[method_id]:
            _fail("method_family_drift", "$method.family", method_id)
        if {field: method.get(field) for field in _PROVIDER_FIELDS} != _EXPECTED_PROVIDER:
            _fail("provider_contract_drift", f"$method[{method_id}]", "frozen provider/model/auth settings changed")
    return methods[0], methods[1]


def _surface(method_id: str) -> dict[str, object]:
    common: dict[str, object] = {
        "visible_task_schema": "tracepixel.b0-visible-task.v1",
        "pixel_program_schema": "tracepixel.pixel-program.v1",
        "operation_vocabulary": ["set_pixels"],
        "deterministic_feedback_schema": B0_DETERMINISTIC_FEEDBACK_SCHEMA_V1,
    }
    if method_id == B0_TRACEPIXEL_METHOD_ID:
        return {
            **common,
            "kind": "tracepixel-staged-agent",
            "art_intent_schema": "tracepixel.art-intent.v1",
            "observation_schema": "tracepixel.agent-observation.v1",
            "proposal_envelope_schema": "tracepixel.agent-provider-proposal.v1",
            "stage_sequence": list(B0_STAGE_SEQUENCE_V1),
            "stage_guidance": True,
        }
    if method_id == B0_RAW_METHOD_ID:
        return {**common, "kind": "raw-pixel-program"}
    _fail("unknown_method", "$method_id", method_id)


def build_b0_method_adapter(preregistration: Mapping[str, object], method_id: str) -> B0MethodAdapterV1:
    staged, raw = validate_b0_scored_methods(preregistration)
    method = staged if method_id == B0_TRACEPIXEL_METHOD_ID else raw if method_id == B0_RAW_METHOD_ID else None
    if method is None:
        _fail("unknown_method", "$method_id", method_id)
    adapter: B0MethodAdapterV1 = {
        "schema": B0_METHOD_ADAPTER_SCHEMA_V1,
        "method_id": method_id,
        "family": _text(method.get("family"), "$method.family"),
        "provider": {field: deepcopy(method[field]) for field in _PROVIDER_FIELDS},
        "authoring_surface": _surface(method_id),
    }
    _validate_json(adapter, "$adapter")
    return adapter


def _art_intent_from_visible_task(task: B0VisibleTaskV1) -> dict[str, object]:
    text, lowered = task["visible_text"], task["visible_text"].lower()
    canvas = re.search(r"\b(\d+)x(\d+)\b", text)
    palette = re.search(r"at most (\d+) visible colors", text, flags=re.IGNORECASE)
    if canvas is None or palette is None:
        _fail("visible_task_unparseable", "$visible_task.visible_text", "staged adapter requires explicit canvas and palette text")

    symmetry: dict[str, object] | None = None
    if "symmetric horizontally and vertically" in lowered:
        symmetry = {"axis": "both", "strength": "required"}
    elif "vertically symmetric" in lowered:
        symmetry = {"axis": "vertical", "strength": "required"}
    elif "horizontally symmetric" in lowered:
        symmetry = {"axis": "horizontal", "strength": "required"}
    facing = "front" if "front-facing" in lowered else "right" if "facing right" in lowered else "left" if "facing left" in lowered else None

    intent = {
        "schema": "tracepixel.art-intent.v1",
        "asset_class": f"b0-benchmark-{task['task_id'].lower()}",
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
        _fail("invalid_visible_derived_art_intent", "$visible_task.visible_text", f"{exc.code}: {exc.message}")
    return intent


def _matched_budget(preregistration: Mapping[str, object]) -> dict[str, object]:
    budgets = _dict(preregistration.get("budgets"), "$preregistration.budgets")
    if any(field not in budgets for field in _MATCHED_BUDGET_FIELDS):
        _fail("budget_contract_drift", "$preregistration.budgets", "missing frozen matched budget")
    return {field: deepcopy(budgets[field]) for field in _MATCHED_BUDGET_FIELDS}


def empty_b0_deterministic_feedback() -> B0DeterministicFeedbackV1:
    return {"schema": B0_DETERMINISTIC_FEEDBACK_SCHEMA_V1, "available": False, "findings": [], "all_rules_pass": None}


def validate_b0_deterministic_feedback(feedback: object) -> B0DeterministicFeedbackV1:
    root = _dict(feedback, "$feedback")
    if frozenset(root) != frozenset(("schema", "available", "findings", "all_rules_pass")):
        _fail("invalid_fields", "$feedback", "feedback fields must match v1 exactly")
    if root["schema"] != B0_DETERMINISTIC_FEEDBACK_SCHEMA_V1 or type(root["available"]) is not bool:
        _fail("invalid_feedback", "$feedback", "schema/available field is invalid")
    findings = _list(root["findings"], "$feedback.findings")
    if root["available"] is False:
        if findings or root["all_rules_pass"] is not None:
            _fail("unavailable_feedback_has_facts", "$feedback", "unavailable feedback must contain no QA facts")
    elif type(root["all_rules_pass"]) is not bool:
        _fail("invalid_feedback", "$feedback.all_rules_pass", "available feedback requires a boolean")
    _validate_json(root, "$feedback")
    return cast(B0DeterministicFeedbackV1, feedback)


def build_b0_provider_request(
    preregistration: Mapping[str, object], *, identity: B0AttemptIdentityV1,
    deterministic_feedback: B0DeterministicFeedbackV1 | None = None, current_stage: str | None = None,
) -> B0ProviderRequestV1:
    identity = validate_attempt_identity(identity, preregistration)
    adapter = build_b0_method_adapter(preregistration, identity["method_id"])
    visible_task = visible_task_packet(preregistration, identity["task_id"])
    feedback = empty_b0_deterministic_feedback() if deterministic_feedback is None else validate_b0_deterministic_feedback(deterministic_feedback)

    if identity["method_id"] == B0_TRACEPIXEL_METHOD_ID:
        current_stage = B0_STAGE_SEQUENCE_V1[0] if current_stage is None else current_stage
        if current_stage not in B0_STAGE_SEQUENCE_V1:
            _fail("invalid_stage", "$current_stage", str(current_stage))
    elif current_stage is not None:
        _fail("raw_stage_guidance_forbidden", "$current_stage", "raw baseline may not receive a TracePixel stage")

    request: B0ProviderRequestV1 = {
        "schema": B0_PROVIDER_REQUEST_SCHEMA_V1,
        "attempt": {
            "attempt_id": identity["attempt_id"], "method_id": identity["method_id"],
            "task_id": identity["task_id"], "trial_index": identity["trial_index"], "rerun_index": identity["rerun_index"],
        },
        "visible_task": visible_task,
        "provider": deepcopy(adapter["provider"]),
        "matched_budget": _matched_budget(preregistration),
        "authoring_surface": deepcopy(adapter["authoring_surface"]),
        "deterministic_feedback": deepcopy(feedback),
    }
    if identity["method_id"] == B0_TRACEPIXEL_METHOD_ID:
        assert current_stage is not None
        request["current_stage"] = current_stage
        request["method_context"] = {
            "art_intent": _art_intent_from_visible_task(visible_task),
            "observation_seed": {
                "schema": "tracepixel.b0-staged-observation-seed.v1",
                "current_stage": current_stage,
                "deterministic_feedback": deepcopy(feedback),
            },
        }
    _validate_json(request, "$request")
    return request


def _pixel_program_schema() -> dict[str, object]:
    pixel = {"type": "array", "items": {"type": "integer"}, "minItems": 6, "maxItems": 6}
    operation = {
        "type": "object", "additionalProperties": False, "required": ["op", "pixels"],
        "properties": {"op": {"type": "string", "const": "set_pixels"}, "pixels": {"type": "array", "items": pixel}},
    }
    return {
        "type": "object", "additionalProperties": False, "required": ["schema", "canvas", "operations"],
        "properties": {
            "schema": {"type": "string", "const": "tracepixel.pixel-program.v1"},
            "canvas": {
                "type": "object", "additionalProperties": False, "required": ["width", "height"],
                "properties": {"width": {"type": "integer"}, "height": {"type": "integer"}},
            },
            "operations": {"type": "array", "items": operation},
        },
    }


def b0_provider_output_schema(method_id: str) -> dict[str, object]:
    program = _pixel_program_schema()
    if method_id == B0_RAW_METHOD_ID:
        return program
    if method_id == B0_TRACEPIXEL_METHOD_ID:
        return {
            "type": "object", "additionalProperties": False, "required": ["schema", "kind", "payload"],
            "properties": {
                "schema": {"type": "string", "const": "tracepixel.agent-provider-proposal.v1"},
                "kind": {"type": "string", "const": "pixel_program"}, "payload": program,
            },
        }
    _fail("unknown_method", "$method_id", method_id)


def normalize_b0_provider_output(method_id: str, output: object) -> dict[str, object]:
    root = _dict(output, "$provider_output")
    if method_id == B0_TRACEPIXEL_METHOD_ID:
        if frozenset(root) != frozenset(("schema", "kind", "payload")) or root.get("schema") != "tracepixel.agent-provider-proposal.v1" or root.get("kind") != "pixel_program":
            _fail("invalid_staged_output", "$provider_output", "expected the pixel_program Agent proposal envelope")
        program = _dict(root["payload"], "$provider_output.payload")
    elif method_id == B0_RAW_METHOD_ID:
        program = root
    else:
        _fail("unknown_method", "$method_id", method_id)
    try:
        validate_pixel_program(program)
    except PixelProgramValidationError as exc:
        _fail("invalid_pixel_program", "$provider_output", f"{exc.code}: {exc.message}")
    _validate_json(program, "$provider_output")
    return deepcopy(program)


def render_b0_codex_prompt(request: B0ProviderRequestV1) -> str:
    if request.get("schema") != B0_PROVIDER_REQUEST_SCHEMA_V1:
        _fail("unsupported_schema", "$request.schema", B0_PROVIDER_REQUEST_SCHEMA_V1)
    _validate_json(request, "$request")
    method_id = _text(_dict(request.get("attempt"), "$request.attempt").get("method_id"), "$request.attempt.method_id")
    if method_id == B0_TRACEPIXEL_METHOD_ID:
        prefix = (
            "Act only as the frozen TracePixel staged B0 authoring adapter. Use the visible task, TracePixel stage identity, "
            "staged authoring surface, and deterministic feedback in the request. Do not inspect the filesystem, run shell commands, "
            "use vision, or add hidden task assumptions. Return exactly one tracepixel.agent-provider-proposal.v1 pixel_program envelope using only set_pixels."
        )
    elif method_id == B0_RAW_METHOD_ID:
        prefix = (
            "Act only as the frozen raw PixelProgram B0 baseline. Use the visible task and deterministic feedback in the request. "
            "Do not inspect the filesystem, run shell commands, use vision, or add hidden task assumptions. "
            "Return exactly one tracepixel.pixel-program.v1 using only set_pixels."
        )
    else:
        _fail("unknown_method", "$request.attempt.method_id", method_id)
    payload = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}\nB0_REQUEST={payload}"


def build_b0_codex_exec_plan(request: B0ProviderRequestV1) -> B0CodexExecPlanV1:
    provider = _dict(request.get("provider"), "$request.provider")
    if {field: provider.get(field) for field in _PROVIDER_FIELDS} != _EXPECTED_PROVIDER:
        _fail("provider_contract_drift", "$request.provider", "request provider settings do not match B0-F0")
    budget = _dict(request.get("matched_budget"), "$request.matched_budget")
    timeout = budget.get("provider_call_timeout_seconds")
    if type(timeout) is not int or cast(int, timeout) <= 0:
        _fail("invalid_timeout", "$request.matched_budget.provider_call_timeout_seconds", "must be positive")
    method_id = _text(_dict(request.get("attempt"), "$request.attempt").get("method_id"), "$request.attempt.method_id")
    command = [
        "codex", "exec", "--ephemeral", "--json", "--skip-git-repo-check", "--sandbox", "read-only",
        "--model", cast(str, provider["model"]), "--config", f"model_reasoning_effort={provider['reasoning_effort']}",
        "--output-schema", "<B0_OUTPUT_SCHEMA_PATH>", "--output-last-message", "<B0_OUTPUT_PATH>", "-",
    ]
    return {
        "schema": B0_CODEX_EXEC_PLAN_SCHEMA_V1,
        "version_check": ["codex", "--version"],
        "expected_version": cast(str, provider["codex_cli_version"]),
        "auth_check": ["codex", "login", "status"],
        "required_auth_marker": "Logged in using ChatGPT",
        "forbid_api_key_auth": True,
        "command": command,
        "timeout_seconds": cast(int, timeout),
        "output_schema": b0_provider_output_schema(method_id),
        "prompt": render_b0_codex_prompt(request),
    }
