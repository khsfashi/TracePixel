from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import time
from typing import Mapping, Sequence, cast

from tracepixel.model import STAGE_SEQUENCE_V1, execute_pixel_program
from tracepixel.qa import analyze_color, analyze_connectivity, analyze_shape_outline, analyze_structural
from tracepixel.raster import Canvas, export_native_png, export_nearest_preview_png

from .b1_adapters import (
    B1_RAW_METHOD_ID,
    B1_TRACEPIXEL_METHOD_ID,
    B1CodexCall,
    B1DeterministicFeedbackV1,
    build_b1_provider_request,
    normalize_b1_provider_output,
)
from .b1_harness import attempt_relative_path, validate_b1_attempt_identity
from .b1_scored import build_b1_attempt_record

B1_DETERMINISTIC_QA_SCHEMA_V1 = "tracepixel.b1-deterministic-qa.v1"
B1_PROVIDER_REQUESTS_SCHEMA_V1 = "tracepixel.b1-provider-requests.v1"
B1_PROVIDER_RESPONSES_SCHEMA_V1 = "tracepixel.b1-provider-responses.v1"
B1_PROPOSAL_OR_FAILURE_SCHEMA_V1 = "tracepixel.b1-proposal-or-failure.v1"
B1_COMPLEXITY_SCHEMA_V1 = "tracepixel.b1-complexity.v1"

B1_REQUIRED_PAYLOAD_FILES = frozenset(
    (
        "attempt-record.json",
        "provider-request.json",
        "provider-response.json",
        "proposal-or-failure.json",
        "deterministic-qa.json",
        "complexity.json",
    )
)
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


class B1RunnerContractError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{message} [{code}]")


def _fail(code: str, message: str) -> None:
    raise B1RunnerContractError(code, message)


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


def _applicable_structural_rules(preregistration: Mapping[str, object], task_id: str) -> tuple[str, ...]:
    task = _tasks(preregistration).get(task_id)
    if task is None:
        _fail("unknown_task", task_id)
    constraints = _dict(task.get("hidden_structural_constraints"), f"{task_id}.hidden_structural_constraints")
    return tuple(sorted(constraints))


def validate_b1_scoring_contract(preregistration: Mapping[str, object]) -> None:
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
        actual = {
            side: _int(margin_map.get(side), f"margins.{side}")
            for side in ("left", "top", "right", "bottom")
        }
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


def score_b1_canvas(
    preregistration: Mapping[str, object],
    task_id: str,
    canvas: Canvas,
) -> dict[str, object]:
    validate_b1_scoring_contract(preregistration)
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
    for rule in _applicable_structural_rules(preregistration, task_id):
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
        checks.append(
            {
                "rule": rule,
                "passed": passed,
                "expected": deepcopy(expected),
                "actual": deepcopy(actual),
            }
        )

    return {
        "schema": B1_DETERMINISTIC_QA_SCHEMA_V1,
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


def b1_feedback_from_qa(qa: Mapping[str, object]) -> B1DeterministicFeedbackV1:
    if qa.get("schema") != B1_DETERMINISTIC_QA_SCHEMA_V1:
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
        "schema": "tracepixel.b1-deterministic-feedback.v1",
        "available": True,
        "findings": findings,
        "all_rules_pass": qa.get("all_rules_pass") is True,
    }


def b1_program_cost(program: Mapping[str, object]) -> tuple[int, int]:
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
    return sum(
        previous[offset : offset + 4] != current[offset : offset + 4]
        for offset in range(0, len(current), 4)
    )


@dataclass(frozen=True, slots=True)
class B1AttemptExecution:
    record: dict[str, object]
    payloads: dict[str, bytes]


def _sum_optional(values: Sequence[int | None]) -> int | None:
    return sum(cast(Sequence[int], values)) if all(value is not None for value in values) else None


def _json_payload(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _complexity(
    *,
    calls: Sequence[B1CodexCall],
    provider_calls: int,
    iterations: int,
    accepted_artifacts: int,
    operation_calls: int,
    pixel_edits: int,
    changed_pixels: int | None,
    stage_decisions: Sequence[Mapping[str, object]],
    repair_cycles: int | None,
    wall_time_ms: int,
    failure_category: str | None,
    runner_commit: str | None,
) -> dict[str, object]:
    authored_stages = sum(item.get("status") == "applied" for item in stage_decisions)
    skipped_stages = sum(item.get("status") == "skipped" for item in stage_decisions)
    return {
        "schema": B1_COMPLEXITY_SCHEMA_V1,
        "input_tokens": _sum_optional([call.input_tokens for call in calls]),
        "output_tokens": _sum_optional([call.output_tokens for call in calls]),
        "provider_calls": provider_calls,
        "tool_calls": _sum_optional([call.tool_calls for call in calls]),
        "operation_calls": operation_calls,
        "pixel_edits": pixel_edits,
        "visual_observation_calls": 0,
        "iterations": iterations,
        "revisions": max(0, accepted_artifacts - 1),
        "changed_pixels": changed_pixels,
        "changed_operations": None,
        "repair_cycles": repair_cycles,
        "authored_stages": authored_stages if repair_cycles is not None else None,
        "skipped_stages": skipped_stages if repair_cycles is not None else None,
        "unaffected_region_stability": None,
        "wall_time_ms": wall_time_ms,
        "api_cost_usd_micros": None,
        "human_interventions": 0,
        "failure_category": failure_category,
        "runner_commit": runner_commit,
    }


def _failure_payload(category: str, code: str, message: str) -> dict[str, object]:
    return {
        "schema": B1_PROPOSAL_OR_FAILURE_SCHEMA_V1,
        "status": "failure",
        "failure_category": category,
        "code": code,
        "message": message,
    }


def _unavailable_qa(task_id: str) -> dict[str, object]:
    return {
        "schema": B1_DETERMINISTIC_QA_SCHEMA_V1,
        "task_id": task_id,
        "available": False,
        "checks": [],
        "rule_results": {},
        "all_rules_pass": False,
    }


def run_b1_attempt(
    preregistration: Mapping[str, object],
    *,
    identity: object,
    executor: object,
    runner_commit: str | None = None,
) -> B1AttemptExecution:
    """Run one frozen B1 primary attempt without manual or selective intervention."""

    identity = validate_b1_attempt_identity(identity, preregistration)
    validate_b1_scoring_contract(preregistration)
    budgets = _dict(preregistration.get("budgets"), "preregistration.budgets")
    max_calls = _int(budgets.get("max_provider_calls_per_trial"), "max_provider_calls_per_trial")
    max_iterations = _int(budgets.get("max_iterations_per_trial"), "max_iterations_per_trial")
    max_tools = _int(budgets.get("max_tool_calls_per_trial"), "max_tool_calls_per_trial")
    max_operations = _int(budgets.get("max_operations_per_trial"), "max_operations_per_trial")
    max_edits = _int(budgets.get("max_pixel_edits_per_trial"), "max_pixel_edits_per_trial")
    max_input = _int(
        budgets.get("max_reported_input_tokens_per_provider_call"),
        "max_reported_input_tokens_per_provider_call",
    )
    max_output = _int(
        budgets.get("max_reported_output_tokens_per_provider_call"),
        "max_reported_output_tokens_per_provider_call",
    )
    wall_limit_ms = _int(budgets.get("trial_wall_timeout_seconds"), "trial_wall_timeout_seconds") * 1000

    method_id = cast(str, identity["method_id"])
    tracepixel = method_id == B1_TRACEPIXEL_METHOD_ID
    started = time.monotonic()
    calls: list[B1CodexCall] = []
    request_records: list[dict[str, object]] = []
    response_records: list[dict[str, object]] = []
    feedback: B1DeterministicFeedbackV1 | None = None
    last_qa: dict[str, object] | None = None
    last_program: dict[str, object] | None = None
    last_output: object | None = None
    last_canvas: Canvas | None = None
    previous_rgba: bytes | None = None
    provider_calls = 0
    iterations = 0
    accepted_artifacts = 0
    operation_calls = 0
    pixel_edits = 0
    changed_pixels: int | None = 0
    total_tools = 0
    stage_decisions: list[dict[str, object]] = []
    repair_cycles = 0
    failure: tuple[str, str, str] | None = None

    while provider_calls < max_calls and iterations < max_iterations:
        iterations += 1
        authoring_stage = (
            STAGE_SEQUENCE_V1[len(stage_decisions)]
            if tracepixel and len(stage_decisions) < len(STAGE_SEQUENCE_V1)
            else None
        )
        current_stage = (
            authoring_stage
            if authoring_stage is not None
            else STAGE_SEQUENCE_V1[-1]
            if tracepixel
            else None
        )
        request = build_b1_provider_request(
            preregistration,
            identity=identity,
            deterministic_feedback=feedback,
            current_stage=current_stage,
        )

        transport_attempt = 0
        call: B1CodexCall | None = None
        while provider_calls < max_calls:
            transport_attempt += 1
            provider_calls += 1
            request_records.append(
                {
                    "iteration": iterations,
                    "transport_attempt": transport_attempt,
                    "authoring_stage": authoring_stage,
                    "post_stage_repair": tracepixel and authoring_stage is None,
                    "request": deepcopy(request),
                }
            )
            call = cast(object, executor).invoke(request, call_index=provider_calls)
            if not isinstance(call, B1CodexCall):
                _fail("invalid_executor", "executor.invoke must return B1CodexCall")
            calls.append(call)
            response_records.append(call.record(provider_calls))
            if call.tool_calls is not None:
                total_tools += call.tool_calls
            if (
                call.status in _RETRYABLE_CALL_STATUSES
                and call.raw_output is None
                and transport_attempt == 1
                and provider_calls < max_calls
            ):
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
            failure = (
                "transport_provider_failure",
                call.error_code or "transport_failure",
                "provider transport failed without usable proposal bytes",
            )
            break
        if call.output is None:
            failure = ("invalid_operation_or_ir", "invalid_provider_json", "provider returned unusable JSON bytes")
            break

        try:
            program = normalize_b1_provider_output(method_id, call.output)
            proposed_operations, proposed_edits = b1_program_cost(program)
        except Exception as exc:
            failure = ("invalid_operation_or_ir", type(exc).__name__, str(exc))
            break
        if operation_calls + proposed_operations > max_operations or pixel_edits + proposed_edits > max_edits:
            failure = (
                "budget_exhaustion",
                "pixel_program_budget",
                "cumulative accepted operation/pixel-edit budget would be exceeded",
            )
            break

        operation_calls += proposed_operations
        pixel_edits += proposed_edits

        if tracepixel and authoring_stage is not None and proposed_edits == 0:
            stage_decisions.append(
                {
                    "stage": authoring_stage,
                    "status": "skipped",
                    "skip_reason": "Provider emitted zero pixel edits for this frozen stage.",
                }
            )
            if last_qa is not None:
                feedback = b1_feedback_from_qa(last_qa)
            if len(stage_decisions) == len(STAGE_SEQUENCE_V1) and last_qa is not None and last_qa["all_rules_pass"] is True:
                break
            continue

        if tracepixel and authoring_stage is None and proposed_edits == 0:
            repair_cycles += 1
            break

        try:
            canvas = execute_pixel_program(program)
            qa = score_b1_canvas(preregistration, cast(str, identity["task_id"]), canvas)
        except Exception as exc:
            failure = ("deterministic_verifier_rejection", type(exc).__name__, str(exc))
            break

        rgba = canvas.rgba_bytes()
        delta_changed = changed_pixel_count(previous_rgba, rgba)
        if changed_pixels is not None:
            changed_pixels = None if delta_changed is None else changed_pixels + delta_changed
        previous_rgba = rgba
        accepted_artifacts += 1
        last_program = program
        last_output = deepcopy(call.output)
        last_canvas = canvas
        last_qa = qa
        feedback = b1_feedback_from_qa(qa)

        if tracepixel and authoring_stage is not None:
            stage_decisions.append(
                {"stage": authoring_stage, "status": "applied", "skip_reason": None}
            )
            if len(stage_decisions) < len(STAGE_SEQUENCE_V1):
                continue
            if qa["all_rules_pass"] is True:
                break
            continue

        if tracepixel:
            repair_cycles += 1
            if qa["all_rules_pass"] is True:
                break
            continue

        if qa["all_rules_pass"] is True:
            break

    wall_time_ms = int((time.monotonic() - started) * 1000)
    if failure is None and last_canvas is None:
        failure = (
            "transport_provider_failure",
            "no_usable_proposal",
            "attempt ended without an accepted artifact",
        )
    if failure is None and tracepixel and len(stage_decisions) < len(STAGE_SEQUENCE_V1):
        failure = (
            "budget_exhaustion",
            "stage_completion_budget",
            "frozen call/iteration budget ended before all six authoring stages were applied or skipped",
        )

    failure_category = None if failure is None else failure[0]
    complexity = _complexity(
        calls=calls,
        provider_calls=provider_calls,
        iterations=iterations,
        accepted_artifacts=accepted_artifacts,
        operation_calls=operation_calls,
        pixel_edits=pixel_edits,
        changed_pixels=changed_pixels,
        stage_decisions=stage_decisions,
        repair_cycles=repair_cycles if tracepixel else None,
        wall_time_ms=wall_time_ms,
        failure_category=failure_category,
        runner_commit=runner_commit,
    )
    completion = failure is None
    record = build_b1_attempt_record(
        preregistration,
        identity=identity,
        completion=completion,
        failure_category=failure_category,
        deterministic_qa=last_qa,
        complexity=complexity,
        stage_decisions=stage_decisions,
        repair_evidence=None,
    )

    if failure is None:
        assert last_canvas is not None and last_program is not None and last_qa is not None
        proposal = {
            "schema": B1_PROPOSAL_OR_FAILURE_SCHEMA_V1,
            "status": "completed",
            "provider_output": last_output,
            "pixel_program": last_program,
        }
    else:
        proposal = _failure_payload(*failure)

    qa_payload = last_qa if last_qa is not None else _unavailable_qa(cast(str, identity["task_id"]))
    payloads = {
        "attempt-record.json": _json_payload(record),
        "provider-request.json": _json_payload(
            {"schema": B1_PROVIDER_REQUESTS_SCHEMA_V1, "calls": request_records}
        ),
        "provider-response.json": _json_payload(
            {"schema": B1_PROVIDER_RESPONSES_SCHEMA_V1, "calls": response_records}
        ),
        "proposal-or-failure.json": _json_payload(proposal),
        "deterministic-qa.json": _json_payload(qa_payload),
        "complexity.json": _json_payload(complexity),
    }
    if completion:
        assert last_canvas is not None
        payloads["final.rgba"] = last_canvas.rgba_bytes()
        payloads["final.png"] = export_native_png(last_canvas).png
        payloads["preview-8x.png"] = export_nearest_preview_png(last_canvas, scale=8).png
    return B1AttemptExecution(record=record, payloads=payloads)


def write_b1_attempt_execution(
    results_root: str | Path,
    preregistration: Mapping[str, object],
    execution: B1AttemptExecution,
) -> Path:
    identity = validate_b1_attempt_identity(execution.record.get("attempt"), preregistration)
    if execution.payloads.get("attempt-record.json") != _json_payload(execution.record):
        _fail("attempt_record_mismatch", "attempt-record.json does not match the retained B1 record")
    missing = B1_REQUIRED_PAYLOAD_FILES - frozenset(execution.payloads)
    if missing:
        _fail("missing_required_artifact", f"missing B1 payloads: {sorted(missing)!r}")
    for name, payload in execution.payloads.items():
        if type(name) is not str or not name or Path(name).name != name or name.startswith("."):
            _fail("invalid_artifact_name", repr(name))
        if type(payload) is not bytes:
            _fail("invalid_artifact_payload", name)

    target = Path(results_root) / attempt_relative_path(identity)
    target.mkdir(parents=True, exist_ok=False)
    for name, payload in execution.payloads.items():
        (target / name).write_bytes(payload)
    index = {
        "schema": "tracepixel.b1-retention-index.v1",
        "attempt_id": identity["attempt_id"],
        "files": {
            name: {"sha256": sha256(payload).hexdigest(), "bytes": len(payload)}
            for name, payload in sorted(execution.payloads.items())
        },
    }
    (target / "retention-index.json").write_bytes(_json_payload(index))
    return target
