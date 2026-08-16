from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Mapping, Sequence, cast

from tracepixel.model import execute_pixel_program
from tracepixel.qa import analyze_color, analyze_connectivity, analyze_shape_outline, analyze_structural
from tracepixel.raster import Canvas, export_native_png, export_nearest_preview_png

from .b0_adapters import (
    B0_RAW_METHOD_ID,
    B0_STAGE_SEQUENCE_V1,
    B0_TRACEPIXEL_METHOD_ID,
    B0DeterministicFeedbackV1,
    B0ProviderRequestV1,
    build_b0_codex_exec_plan,
    build_b0_provider_request,
    normalize_b0_provider_output,
)
from .b0_harness import (
    B0AttemptIdentityV1,
    B0AttemptResultV1,
    applicable_structural_rules,
    build_attempt_result,
    json_payload,
    validate_attempt_identity,
)

B0_DETERMINISTIC_QA_SCHEMA_V1 = "tracepixel.b0-deterministic-qa.v1"
B0_PROVIDER_RESPONSE_SCHEMA_V1 = "tracepixel.b0-provider-response.v1"
B0_PROPOSAL_OR_FAILURE_SCHEMA_V1 = "tracepixel.b0-proposal-or-failure.v1"
B0_TELEMETRY_SCHEMA_V1 = "tracepixel.b0-telemetry.v1"
B0_CODEX_CALL_SCHEMA_V1 = "tracepixel.b0-codex-call.v1"

_SUPPORTED_RULES = frozenset(
    (
        "width",
        "height",
        "transparent_background",
        "minimum_margin_each_side",
        "maximum_visible_colors",
        "connected_components",
        "maximum_isolated_visible_pixels",
        "horizontal_symmetry",
        "vertical_symmetry",
        "edge_contact_allowed",
    )
)
_RETRYABLE_CALL_STATUSES = frozenset(("timeout", "transport_failure"))
_TOOL_ITEM_TYPES = frozenset(
    (
        "command_execution",
        "mcp_tool_call",
        "web_search",
        "file_search",
        "image_generation",
    )
)


class B0ScoredContractError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{message} [{code}]")


def _fail(code: str, message: str) -> None:
    raise B0ScoredContractError(code, message)


def _dict(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict or not all(type(key) is str for key in cast(dict[object, object], value)):
        _fail("invalid_contract", f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _int(value: object, label: str) -> int:
    if type(value) is not int:
        _fail("invalid_contract", f"{label} must be an integer")
    return cast(int, value)


def _tasks(preregistration: Mapping[str, object]) -> dict[str, dict[str, object]]:
    raw = preregistration.get("tasks")
    if type(raw) is not list:
        _fail("invalid_contract", "preregistration.tasks must be an array")
    result: dict[str, dict[str, object]] = {}
    for item in cast(list[object], raw):
        task = _dict(item, "task")
        task_id = task.get("id")
        if type(task_id) is not str or not task_id:
            _fail("invalid_contract", "task.id must be a non-empty string")
        result[cast(str, task_id)] = task
    return result


def validate_b0_scoring_contract(preregistration: Mapping[str, object]) -> None:
    """Fail before scoring if B0 contains a deterministic rule this runner cannot score."""
    for task_id, task in _tasks(preregistration).items():
        constraints = _dict(task.get("hidden_structural_constraints"), f"{task_id}.hidden_structural_constraints")
        unsupported = frozenset(constraints) - _SUPPORTED_RULES
        if unsupported:
            _fail("unsupported_structural_rule", f"{task_id} contains unsupported rules: {sorted(unsupported)!r}")
        if constraints.get("transparent_background") is not True:
            _fail("unsupported_background_rule", f"{task_id} must retain the frozen transparent background rule")
        if constraints.get("edge_contact_allowed") not in (False, None):
            _fail("unsupported_edge_rule", f"{task_id} edge_contact_allowed=true is not a required-contact rule")


def _required_symmetry(constraints: Mapping[str, object]) -> str | None:
    horizontal = constraints.get("horizontal_symmetry") is True
    vertical = constraints.get("vertical_symmetry") is True
    if horizontal and vertical:
        return "both"
    if vertical:
        return "vertical"
    if horizontal:
        return "horizontal"
    return None


def _rule_detail(
    rule: str,
    expected: object,
    *,
    structural: Mapping[str, object],
    color: Mapping[str, object],
    connectivity: Mapping[str, object],
    shape: Mapping[str, object],
) -> tuple[bool, object]:
    dimensions = _dict(structural.get("dimensions"), "structural.dimensions")
    alpha = _dict(structural.get("alpha"), "structural.alpha")
    edge = _dict(structural.get("edge_contact"), "structural.edge_contact")
    margins = structural.get("margins")

    if rule == "width":
        actual = dimensions.get("width")
        return actual == expected, actual
    if rule == "height":
        actual = dimensions.get("height")
        return actual == expected, actual
    if rule == "transparent_background":
        actual = _int(alpha.get("transparent_pixels"), "structural.alpha.transparent_pixels")
        return actual > 0, {"transparent_pixels": actual}
    if rule == "minimum_margin_each_side":
        if type(margins) is not dict:
            return False, None
        margin_map = cast(dict[str, object], margins)
        actual = {side: _int(margin_map.get(side), f"margins.{side}") for side in ("left", "top", "right", "bottom")}
        minimum = _int(expected, "minimum_margin_each_side")
        return all(value >= minimum for value in actual.values()), actual
    if rule == "maximum_visible_colors":
        colors = _dict(color.get("colors"), "color.colors")
        actual = _int(colors.get("visible_rgba_colors"), "color.colors.visible_rgba_colors")
        return actual <= _int(expected, "maximum_visible_colors"), actual
    if rule == "connected_components":
        components = _dict(connectivity.get("components"), "connectivity.components")
        actual = _int(components.get("count"), "connectivity.components.count")
        return actual == expected, actual
    if rule == "maximum_isolated_visible_pixels":
        isolated = _dict(connectivity.get("isolated_pixels"), "connectivity.isolated_pixels")
        actual = _int(isolated.get("count"), "connectivity.isolated_pixels.count")
        return actual <= _int(expected, "maximum_isolated_visible_pixels"), actual
    if rule in ("horizontal_symmetry", "vertical_symmetry"):
        symmetry = _dict(shape.get("symmetry"), "shape.symmetry")
        axis = "horizontal" if rule == "horizontal_symmetry" else "vertical"
        facts = symmetry.get(axis)
        if type(facts) is not dict:
            return False, None
        facts_map = cast(dict[str, object], facts)
        actual = {
            "matches": facts_map.get("matches") is True,
            "mismatched_pairs": facts_map.get("mismatched_pairs"),
        }
        return actual["matches"] is True, actual
    if rule == "edge_contact_allowed":
        actual = edge.get("any") is True
        if expected is False:
            return not actual, actual
        return True, actual
    _fail("unsupported_structural_rule", rule)


def score_b0_canvas(
    preregistration: Mapping[str, object],
    task_id: str,
    canvas: Canvas,
) -> dict[str, object]:
    """Compute all frozen B0 structural rules from deterministic raster QA only."""
    validate_b0_scoring_contract(preregistration)
    task = _tasks(preregistration).get(task_id)
    if task is None:
        _fail("unknown_task", task_id)
    constraints = _dict(task.get("hidden_structural_constraints"), f"{task_id}.hidden_structural_constraints")
    symmetry = _required_symmetry(constraints)
    max_colors = constraints.get("maximum_visible_colors")

    structural = analyze_structural(canvas)
    color = analyze_color(canvas, max_colors=max_colors)
    connectivity = analyze_connectivity(canvas)
    shape = analyze_shape_outline(canvas, required_symmetry=cast(object, symmetry))

    rule_results: dict[str, bool] = {}
    checks: list[dict[str, object]] = []
    for rule in applicable_structural_rules(preregistration, task_id):
        expected = constraints[rule]
        passed, actual = _rule_detail(
            rule,
            expected,
            structural=structural,
            color=color,
            connectivity=connectivity,
            shape=shape,
        )
        rule_results[rule] = passed
        checks.append({"rule": rule, "passed": passed, "expected": deepcopy(expected), "actual": deepcopy(actual)})

    return {
        "schema": B0_DETERMINISTIC_QA_SCHEMA_V1,
        "task_id": task_id,
        "facts": {
            "structural": structural,
            "color": color,
            "connectivity": connectivity,
            "shape_outline": shape,
        },
        "checks": checks,
        "rule_results": rule_results,
        "all_rules_pass": all(rule_results.values()),
    }


def b0_feedback_from_qa(qa: Mapping[str, object]) -> B0DeterministicFeedbackV1:
    if qa.get("schema") != B0_DETERMINISTIC_QA_SCHEMA_V1:
        _fail("invalid_qa", "deterministic QA schema mismatch")
    checks = qa.get("checks")
    if type(checks) is not list:
        _fail("invalid_qa", "deterministic QA checks must be an array")
    findings: list[dict[str, object]] = []
    for item in cast(list[object], checks):
        if type(item) is not dict:
            continue
        check = cast(dict[str, object], item)
        if check.get("passed") is False:
            findings.append(
                {
                    "rule": deepcopy(check.get("rule")),
                    "passed": False,
                    "actual": deepcopy(check.get("actual")),
                }
            )
    return {
        "schema": "tracepixel.b0-deterministic-feedback.v1",
        "available": True,
        "findings": findings,
        "all_rules_pass": qa.get("all_rules_pass") is True,
    }


def b0_stage_for_iteration(iteration_index: int) -> str:
    if type(iteration_index) is not int or iteration_index < 0:
        _fail("invalid_iteration", "iteration_index must be >= 0")
    return B0_STAGE_SEQUENCE_V1[min(iteration_index, len(B0_STAGE_SEQUENCE_V1) - 1)]


def b0_program_cost(program: Mapping[str, object]) -> tuple[int, int]:
    operations = program.get("operations")
    if type(operations) is not list:
        _fail("invalid_program", "PixelProgram operations must be an array")
    operation_count = len(cast(list[object], operations))
    pixel_edits = 0
    for operation in cast(list[object], operations):
        op = _dict(operation, "operation")
        pixels = op.get("pixels")
        if type(pixels) is not list:
            _fail("invalid_program", "set_pixels.pixels must be an array")
        pixel_edits += len(cast(list[object], pixels))
    return operation_count, pixel_edits


def changed_pixel_count(previous: bytes | None, current: bytes) -> int | None:
    if len(current) % 4:
        _fail("invalid_raster", "RGBA snapshots must use a 4-byte pixel stride")
    if previous is None:
        previous = bytes(len(current))
    if len(previous) != len(current):
        return None
    return sum(previous[offset : offset + 4] != current[offset : offset + 4] for offset in range(0, len(current), 4))


@dataclass(frozen=True, slots=True)
class B0CodexCall:
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
            "schema": B0_CODEX_CALL_SCHEMA_V1,
            "call_index": call_index,
            "status": self.status,
            "returncode": self.returncode,
            "error_code": self.error_code,
            "raw_output": self.raw_output,
            "raw_output_sha256": None if self.raw_output is None else sha256(self.raw_output.encode("utf-8")).hexdigest(),
            "output": deepcopy(self.output),
            "usage": {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens},
            "tool_calls": self.tool_calls,
            "wall_time_ms": self.wall_time_ms,
        }


_Run = Callable[..., subprocess.CompletedProcess[str]]
_Which = Callable[[str], str | None]


class B0CodexExecutor:
    """Exact owner-local executor for the provider boundary frozen by B0-F0."""

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
            _fail("codex_not_found", f"cannot find {self._executable_name!r} on PATH")
        self._resolved = resolved
        return resolved

    @staticmethod
    def _command(executable: str, arguments: Sequence[str]) -> list[str]:
        if Path(executable).suffix.lower() in (".cmd", ".bat"):
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            return [comspec, "/d", "/s", "/c", subprocess.list2cmdline([executable, *arguments])]
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
            _fail("codex_preflight_failed", str(exc))
        if result.returncode != 0:
            _fail("codex_preflight_failed", f"Codex metadata command exited with {result.returncode}")
        return result

    def preflight(self, request: B0ProviderRequestV1) -> dict[str, object]:
        plan = build_b0_codex_exec_plan(request)
        version_result = self._metadata(plan["version_check"][1:])
        version = (version_result.stdout or version_result.stderr).strip()
        if version != plan["expected_version"]:
            _fail("codex_version_mismatch", f"expected {plan['expected_version']!r}, got {version!r}")
        auth_result = self._metadata(plan["auth_check"][1:])
        auth_text = "\n".join(part.strip() for part in (auth_result.stdout, auth_result.stderr) if part.strip())
        if plan["required_auth_marker"] not in auth_text:
            _fail("chatgpt_login_required", f"Codex must report {plan['required_auth_marker']!r}")
        if plan["forbid_api_key_auth"] and "Logged in using an API key" in auth_text:
            _fail("api_key_auth_forbidden", "B0 forbids API-key authenticated provider execution")
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
            if type(item) is dict and cast(dict[str, object], item).get("type") in _TOOL_ITEM_TYPES:
                count += 1
        return count

    def invoke(self, request: B0ProviderRequestV1, *, call_index: int) -> B0CodexCall:
        del call_index  # identity is retained by the caller; the provider prompt remains request-only.
        plan = build_b0_codex_exec_plan(request)
        executable = self._resolve()
        with tempfile.TemporaryDirectory(prefix="tracepixel-b0-") as temporary:
            directory = Path(temporary)
            schema_path = directory / "output.schema.json"
            output_path = directory / "output.json"
            schema_path.write_text(json.dumps(plan["output_schema"], sort_keys=True, separators=(",", ":")), encoding="utf-8")
            arguments = list(plan["command"][1:])
            arguments[arguments.index("<B0_OUTPUT_SCHEMA_PATH>")] = str(schema_path)
            arguments[arguments.index("<B0_OUTPUT_PATH>")] = str(output_path)
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
                return B0CodexCall("timeout", None, None, None, None, None, elapsed, None, "codex_timeout")
            except OSError:
                elapsed = int((time.monotonic() - started) * 1000)
                return B0CodexCall("transport_failure", None, None, None, None, None, elapsed, None, "codex_launch_failed")

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
                return B0CodexCall("transport_failure", None, None, input_tokens, output_tokens, tool_calls, elapsed, result.returncode, code)
            try:
                output: object | None = json.loads(raw_output)
            except json.JSONDecodeError:
                output = None
            return B0CodexCall("response", output, raw_output, input_tokens, output_tokens, tool_calls, elapsed, result.returncode, None)


@dataclass(frozen=True, slots=True)
class B0AttemptExecution:
    result: B0AttemptResultV1
    payloads: dict[str, bytes]


def _sum_optional(values: Sequence[int | None]) -> int | None:
    return sum(cast(Sequence[int], values)) if all(value is not None for value in values) else None


def _telemetry(
    *,
    calls: Sequence[B0CodexCall],
    provider_calls: int,
    iterations: int,
    accepted: int,
    operation_calls: int,
    changed_pixels: int | None,
    wall_time_ms: int,
    failure_category: str | None,
    runner_commit: str | None,
) -> dict[str, object]:
    return {
        "schema": B0_TELEMETRY_SCHEMA_V1,
        "input_tokens": _sum_optional([call.input_tokens for call in calls]),
        "output_tokens": _sum_optional([call.output_tokens for call in calls]),
        "provider_calls": provider_calls,
        "tool_calls": _sum_optional([call.tool_calls for call in calls]),
        "operation_calls": operation_calls,
        "visual_observation_calls": 0,
        "iterations": iterations,
        "revisions": max(0, accepted - 1),
        "changed_pixels": changed_pixels,
        "wall_time_ms": wall_time_ms,
        "api_cost_usd_micros": None,
        "human_interventions": 0,
        "failure_category": failure_category,
        "runner_commit": runner_commit,
    }


def _failure_payload(category: str, code: str, message: str) -> dict[str, object]:
    return {
        "schema": B0_PROPOSAL_OR_FAILURE_SCHEMA_V1,
        "status": "failure",
        "failure_category": category,
        "code": code,
        "message": message,
    }


def run_b0_attempt(
    preregistration: Mapping[str, object],
    *,
    identity: B0AttemptIdentityV1,
    executor: object,
    runner_commit: str | None = None,
) -> B0AttemptExecution:
    """Run one frozen primary B0 attempt without selective/manual intervention."""
    identity = validate_attempt_identity(identity, preregistration)
    validate_b0_scoring_contract(preregistration)
    if identity["rerun_index"] != 0:
        _fail("rerun_requires_void_protocol", "B0-S0 automatic runner accepts primary identities only")
    budgets = _dict(preregistration.get("budgets"), "preregistration.budgets")
    max_calls = _int(budgets.get("max_provider_calls_per_trial"), "max_provider_calls_per_trial")
    max_iterations = _int(budgets.get("max_iterations_per_trial"), "max_iterations_per_trial")
    max_tools = _int(budgets.get("max_tool_calls_per_trial"), "max_tool_calls_per_trial")
    max_operations = _int(budgets.get("max_operations_per_trial"), "max_operations_per_trial")
    max_edits = _int(budgets.get("max_pixel_edits_per_trial"), "max_pixel_edits_per_trial")
    max_input = _int(budgets.get("max_reported_input_tokens_per_provider_call"), "max_reported_input_tokens_per_provider_call")
    max_output = _int(budgets.get("max_reported_output_tokens_per_provider_call"), "max_reported_output_tokens_per_provider_call")
    wall_limit_ms = _int(budgets.get("trial_wall_timeout_seconds"), "trial_wall_timeout_seconds") * 1000

    started = time.monotonic()
    calls: list[B0CodexCall] = []
    request_records: list[dict[str, object]] = []
    response_records: list[dict[str, object]] = []
    feedback: B0DeterministicFeedbackV1 | None = None
    last_qa: dict[str, object] | None = None
    last_program: dict[str, object] | None = None
    last_output: object | None = None
    last_canvas: Canvas | None = None
    previous_rgba: bytes | None = None
    provider_calls = 0
    iterations = 0
    accepted = 0
    operation_calls = 0
    pixel_edits = 0
    changed_pixels: int | None = 0
    total_tools = 0

    failure: tuple[str, str, str] | None = None

    while provider_calls < max_calls and iterations < max_iterations:
        iterations += 1
        current_stage = b0_stage_for_iteration(iterations - 1) if identity["method_id"] == B0_TRACEPIXEL_METHOD_ID else None
        request = build_b0_provider_request(
            preregistration,
            identity=identity,
            deterministic_feedback=feedback,
            current_stage=current_stage,
        )

        transport_attempt = 0
        call: B0CodexCall | None = None
        while provider_calls < max_calls:
            transport_attempt += 1
            provider_calls += 1
            request_records.append(
                {
                    "iteration": iterations,
                    "transport_attempt": transport_attempt,
                    "request": deepcopy(request),
                }
            )
            call = cast(object, executor).invoke(request, call_index=provider_calls)
            if not isinstance(call, B0CodexCall):
                _fail("invalid_executor", "executor.invoke must return B0CodexCall")
            calls.append(call)
            response_records.append(call.record(provider_calls))
            if call.tool_calls is not None:
                total_tools += call.tool_calls
            if call.status in _RETRYABLE_CALL_STATUSES and call.raw_output is None and transport_attempt == 1 and provider_calls < max_calls:
                continue
            break

        assert call is not None
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if elapsed_ms > wall_limit_ms:
            failure = ("timeout", "trial_wall_timeout", "trial wall-time budget was exceeded")
            break
        if call.input_tokens is not None and call.input_tokens > max_input:
            failure = ("budget_exhaustion", "input_token_budget", "reported per-call input tokens exceeded the frozen budget")
            break
        if call.output_tokens is not None and call.output_tokens > max_output:
            failure = ("budget_exhaustion", "output_token_budget", "reported per-call output tokens exceeded the frozen budget")
            break
        if total_tools > max_tools:
            failure = ("budget_exhaustion", "tool_call_budget", "tool-call budget was exceeded")
            break
        if call.status == "timeout":
            failure = ("timeout", call.error_code or "codex_timeout", "provider call timed out without usable proposal bytes")
            break
        if call.status == "transport_failure":
            failure = ("transport_provider_failure", call.error_code or "transport_failure", "provider transport failed without usable proposal bytes")
            break
        if call.output is None:
            failure = ("invalid_operation_or_ir", "invalid_provider_json", "provider returned unusable JSON bytes")
            break

        try:
            program = normalize_b0_provider_output(identity["method_id"], call.output)
            proposed_operations, proposed_edits = b0_program_cost(program)
        except Exception as exc:
            failure = ("invalid_operation_or_ir", type(exc).__name__, str(exc))
            break
        if operation_calls + proposed_operations > max_operations or pixel_edits + proposed_edits > max_edits:
            failure = ("budget_exhaustion", "pixel_program_budget", "cumulative accepted operation/pixel-edit budget would be exceeded")
            break

        try:
            canvas = execute_pixel_program(program)
            qa = score_b0_canvas(preregistration, identity["task_id"], canvas)
        except Exception as exc:
            failure = ("deterministic_verifier_rejection", type(exc).__name__, str(exc))
            break

        rgba = canvas.rgba_bytes()
        delta_changed = changed_pixel_count(previous_rgba, rgba)
        if changed_pixels is not None:
            changed_pixels = None if delta_changed is None else changed_pixels + delta_changed
        previous_rgba = rgba
        operation_calls += proposed_operations
        pixel_edits += proposed_edits
        accepted += 1
        last_program = program
        last_output = deepcopy(call.output)
        last_canvas = canvas
        last_qa = qa

        if qa["all_rules_pass"] is True:
            break
        if operation_calls == max_operations or pixel_edits == max_edits:
            break
        feedback = b0_feedback_from_qa(qa)

    wall_time_ms = int((time.monotonic() - started) * 1000)
    if failure is None and last_canvas is None:
        failure = ("transport_provider_failure", "no_usable_proposal", "attempt ended without an accepted proposal")

    if failure is not None:
        category, code, message = failure
        telemetry = _telemetry(
            calls=calls,
            provider_calls=provider_calls,
            iterations=iterations,
            accepted=accepted,
            operation_calls=operation_calls,
            changed_pixels=changed_pixels,
            wall_time_ms=wall_time_ms,
            failure_category=category,
            runner_commit=runner_commit,
        )
        result = build_attempt_result(
            preregistration,
            identity=identity,
            provider_invoked=provider_calls > 0,
            completion=False,
            failure_category=category,
            rule_results=None,
            telemetry=telemetry,
            notes=f"B0-S0 failure: {code}",
        )
        qa_payload = last_qa or {
            "schema": B0_DETERMINISTIC_QA_SCHEMA_V1,
            "task_id": identity["task_id"],
            "available": False,
            "rule_results": {rule: False for rule in applicable_structural_rules(preregistration, identity["task_id"])},
            "all_rules_pass": False,
        }
        if last_qa is not None:
            qa_payload = {**last_qa, "scored_as_zero_due_noncompletion": True}
        payloads = {
            "provider-request.json": json_payload({"schema": "tracepixel.b0-provider-requests.v1", "calls": request_records}),
            "provider-response.json": json_payload({"schema": B0_PROVIDER_RESPONSE_SCHEMA_V1, "calls": response_records}),
            "proposal-or-failure.json": json_payload(_failure_payload(category, code, message)),
            "deterministic-qa.json": json_payload(qa_payload),
            "telemetry.json": json_payload(telemetry),
        }
        return B0AttemptExecution(result=result, payloads=payloads)

    assert last_canvas is not None and last_program is not None and last_qa is not None
    telemetry = _telemetry(
        calls=calls,
        provider_calls=provider_calls,
        iterations=iterations,
        accepted=accepted,
        operation_calls=operation_calls,
        changed_pixels=changed_pixels,
        wall_time_ms=wall_time_ms,
        failure_category=None,
        runner_commit=runner_commit,
    )
    result = build_attempt_result(
        preregistration,
        identity=identity,
        provider_invoked=True,
        completion=True,
        failure_category=None,
        rule_results=cast(dict[str, bool], last_qa["rule_results"]),
        telemetry=telemetry,
        notes="B0-S0 stopped only on deterministic all-rules pass or frozen budget boundary.",
    )
    native = export_native_png(last_canvas)
    preview = export_nearest_preview_png(last_canvas, scale=8)
    payloads = {
        "provider-request.json": json_payload({"schema": "tracepixel.b0-provider-requests.v1", "calls": request_records}),
        "provider-response.json": json_payload({"schema": B0_PROVIDER_RESPONSE_SCHEMA_V1, "calls": response_records}),
        "proposal-or-failure.json": json_payload(
            {
                "schema": B0_PROPOSAL_OR_FAILURE_SCHEMA_V1,
                "status": "completed",
                "provider_output": last_output,
                "pixel_program": last_program,
            }
        ),
        "deterministic-qa.json": json_payload(last_qa),
        "telemetry.json": json_payload(telemetry),
        "final.rgba": last_canvas.rgba_bytes(),
        "final.png": native.png,
        "preview-8x.png": preview.png,
    }
    return B0AttemptExecution(result=result, payloads=payloads)
