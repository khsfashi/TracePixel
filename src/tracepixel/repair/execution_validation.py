from __future__ import annotations

from hashlib import sha256
from typing import cast

from tracepixel.model.execution import _apply_validated_pixel_program
from tracepixel.model.pixel_ir import PixelProgramV1
from tracepixel.qa import MAX_QA_POLICY_RULES_V1, QA_FINDINGS_SCHEMA_V1, QaFindingsV1
from tracepixel.raster import Canvas

from .execution import (
    REPAIR_EXECUTION_SCHEMA_V1,
    RepairExecutionItemV1,
    RepairExecutionV1,
    RepairQaEvaluator,
)
from .plan import RepairPlanV1
from .plan_validation import RepairPlanValidationError, validate_repair_plan

_ROOT_FIELDS = frozenset(
    (
        "schema",
        "plan",
        "source_rgba_sha256",
        "result_rgba_sha256",
        "executions",
        "applied_operation_count",
        "applied_pixel_edit_count",
        "observed_changed_pixel_count",
        "unaffected_region_stable",
        "qa",
    )
)
_EXECUTION_FIELDS = frozenset(
    (
        "feedback_id",
        "status",
        "target_stage",
        "applied_operation_count",
        "applied_pixel_edit_count",
        "observed_changed_pixel_count",
    )
)
_QA_FIELDS = frozenset(("schema", "findings"))
_QA_FINDING_FIELDS = frozenset(("rule", "category", "severity"))
_QA_CATEGORY_BY_RULE = {
    "structural.non_empty": "structural",
    "structural.no_translucency": "structural",
    "structural.no_edge_contact": "structural",
    "color.palette_membership": "color",
    "color.maximum_colors": "color",
    "color.transparent_rgb_policy": "color",
    "connectivity.single_component": "connectivity",
    "connectivity.no_isolated_pixels": "connectivity",
    "shape.required_symmetry": "shape",
    "tile.contract": "tile",
}
_QA_SEVERITIES = frozenset(("info", "warning", "error"))
_HEX_DIGITS = frozenset("0123456789abcdef")


class RepairExecutionValidationError(ValueError):
    """Deterministic P7-F3 rejection with stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise RepairExecutionValidationError(code, path, message)


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


def _require_array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def _require_nonnegative_int(value: object, path: str) -> int:
    if type(value) is not int:
        _fail("invalid_type", path, "must be an integer")
    result = cast(int, value)
    if result < 0:
        _fail("invalid_value", path, "must be >= 0")
    return result


def _require_digest(value: object, path: str) -> str:
    if (
        type(value) is not str
        or len(cast(str, value)) != 64
        or any(char not in _HEX_DIGITS for char in cast(str, value))
    ):
        _fail("invalid_digest", path, "must be 64 lowercase hexadecimal characters")
    return cast(str, value)


def _validated_plan(value: object) -> RepairPlanV1:
    try:
        return validate_repair_plan(value)
    except RepairPlanValidationError as exc:
        path = "$.plan" if exc.path == "$" else f"$.plan{exc.path[1:]}"
        _fail(
            "invalid_plan",
            path,
            f"repair plan validation failed with {exc.code}: {exc.message}",
        )


def _validate_qa_findings(value: object, path: str = "$.qa") -> QaFindingsV1:
    root = _require_exact_object(value, path, _QA_FIELDS)
    if root["schema"] != QA_FINDINGS_SCHEMA_V1:
        _fail(
            "unsupported_qa_schema",
            f"{path}.schema",
            f"expected {QA_FINDINGS_SCHEMA_V1!r}",
        )

    findings = _require_array(root["findings"], f"{path}.findings")
    if len(findings) > MAX_QA_POLICY_RULES_V1:
        _fail(
            "too_many_qa_findings",
            f"{path}.findings",
            f"supports at most {MAX_QA_POLICY_RULES_V1} deterministic findings",
        )

    seen_rules: set[str] = set()
    for index, raw_finding in enumerate(findings):
        item_path = f"{path}.findings[{index}]"
        finding = _require_exact_object(raw_finding, item_path, _QA_FINDING_FIELDS)

        rule = finding["rule"]
        if type(rule) is not str or rule not in _QA_CATEGORY_BY_RULE:
            _fail("invalid_qa_rule", f"{item_path}.rule", "must be a supported Q5 rule")
        rule_value = cast(str, rule)
        if rule_value in seen_rules:
            _fail("duplicate_qa_rule", f"{item_path}.rule", f"duplicate rule {rule_value!r}")
        seen_rules.add(rule_value)

        category = finding["category"]
        if category != _QA_CATEGORY_BY_RULE[rule_value]:
            _fail(
                "qa_category_mismatch",
                f"{item_path}.category",
                "must match the deterministic Q5 rule category",
            )

        severity = finding["severity"]
        if type(severity) is not str or severity not in _QA_SEVERITIES:
            _fail(
                "invalid_qa_severity",
                f"{item_path}.severity",
                "must be info, warning, or error",
            )

    return cast(QaFindingsV1, value)


def _program_stats(program: PixelProgramV1) -> tuple[int, int]:
    operations = program["operations"]
    return len(operations), sum(len(operation["pixels"]) for operation in operations)


def _pack_at(rgba: memoryview, pixel_index: int) -> int:
    offset = pixel_index << 2
    return (
        (rgba[offset] << 24)
        | (rgba[offset + 1] << 16)
        | (rgba[offset + 2] << 8)
        | rgba[offset + 3]
    )


def _capture_touched_pixels(
    canvas: Canvas,
    program: PixelProgramV1,
) -> tuple[dict[int, int], set[int]]:
    """Capture only unique positions touched by one canonical repair program."""

    rgba = canvas._rgba_view()
    width = canvas.width
    before: dict[int, int] = {}
    touched: set[int] = set()
    for operation in program["operations"]:
        for pixel in operation["pixels"]:
            index = pixel[1] * width + pixel[0]
            touched.add(index)
            if index not in before:
                before[index] = _pack_at(rgba, index)
    return before, touched


def _count_changed_touched_pixels(canvas: Canvas, before: dict[int, int]) -> int:
    rgba = canvas._rgba_view()
    return sum(_pack_at(rgba, index) != packed for index, packed in before.items())


def _measure_final_delta(
    *,
    source: bytes,
    canvas: Canvas,
    touched: set[int],
) -> tuple[int, bool]:
    current = canvas._rgba_view()
    changed = 0
    unaffected_region_stable = True
    for index in range(canvas.width * canvas.height):
        offset = index << 2
        differs = (
            source[offset] != current[offset]
            or source[offset + 1] != current[offset + 1]
            or source[offset + 2] != current[offset + 2]
            or source[offset + 3] != current[offset + 3]
        )
        if not differs:
            continue
        changed += 1
        if index not in touched:
            unaffected_region_stable = False
    return changed, unaffected_region_stable


def _planned_write_indices(plan: RepairPlanV1) -> set[int]:
    width = plan["localization"]["intake"]["target"]["canvas"]["width"]
    indices: set[int] = set()
    for repair in plan["repairs"]:
        program = repair["repair_program"]
        if repair["disposition"] != "repair" or program is None:
            continue
        for operation in program["operations"]:
            for pixel in operation["pixels"]:
                indices.add(pixel[1] * width + pixel[0])
    return indices


def validate_repair_execution(value: object) -> RepairExecutionV1:
    """Validate closed F3 provenance, observed cost accounting, and deterministic QA shape."""

    root = _require_exact_object(value, "$", _ROOT_FIELDS)
    if root["schema"] != REPAIR_EXECUTION_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"expected {REPAIR_EXECUTION_SCHEMA_V1!r}",
        )

    plan = _validated_plan(root["plan"])
    _require_digest(root["source_rgba_sha256"], "$.source_rgba_sha256")
    _require_digest(root["result_rgba_sha256"], "$.result_rgba_sha256")

    raw_executions = _require_array(root["executions"], "$.executions")
    if len(raw_executions) != len(plan["repairs"]):
        _fail(
            "execution_count_mismatch",
            "$.executions",
            "must contain exactly one execution record per F2 repair/defer item",
        )

    operation_total = 0
    edit_total = 0
    for index, raw_execution in enumerate(raw_executions):
        path = f"$.executions[{index}]"
        execution = _require_exact_object(raw_execution, path, _EXECUTION_FIELDS)
        repair = plan["repairs"][index]

        if execution["feedback_id"] != repair["feedback_id"]:
            _fail(
                "feedback_order_mismatch",
                f"{path}.feedback_id",
                f"must match F2 item {repair['feedback_id']!r} at the same index",
            )

        operation_count = _require_nonnegative_int(
            execution["applied_operation_count"],
            f"{path}.applied_operation_count",
        )
        edit_count = _require_nonnegative_int(
            execution["applied_pixel_edit_count"],
            f"{path}.applied_pixel_edit_count",
        )
        changed_count = _require_nonnegative_int(
            execution["observed_changed_pixel_count"],
            f"{path}.observed_changed_pixel_count",
        )

        if repair["disposition"] == "defer":
            if (
                execution["status"] != "deferred"
                or execution["target_stage"] is not None
                or operation_count != 0
                or edit_count != 0
                or changed_count != 0
            ):
                _fail(
                    "invalid_deferred_execution",
                    path,
                    "deferred F2 items must remain unexecuted with zero observed cost",
                )
            continue

        if execution["status"] != "applied":
            _fail("invalid_execution_status", f"{path}.status", "active repair must be applied")
        if execution["target_stage"] != repair["target_stage"]:
            _fail(
                "target_stage_mismatch",
                f"{path}.target_stage",
                "must equal the F2 repair target stage",
            )
        if operation_count != repair["planned_operation_count"]:
            _fail(
                "applied_cost_mismatch",
                f"{path}.applied_operation_count",
                "must equal the canonical F2 planned operation count",
            )
        if edit_count != repair["planned_pixel_edit_count"]:
            _fail(
                "applied_cost_mismatch",
                f"{path}.applied_pixel_edit_count",
                "must equal the canonical F2 planned pixel-edit count",
            )
        if changed_count > edit_count:
            _fail(
                "changed_count_out_of_range",
                f"{path}.observed_changed_pixel_count",
                "cannot exceed applied unique pixel edits",
            )

        operation_total += operation_count
        edit_total += edit_count

    reported_operation_total = _require_nonnegative_int(
        root["applied_operation_count"],
        "$.applied_operation_count",
    )
    reported_edit_total = _require_nonnegative_int(
        root["applied_pixel_edit_count"],
        "$.applied_pixel_edit_count",
    )
    if reported_operation_total != operation_total:
        _fail(
            "total_cost_mismatch",
            "$.applied_operation_count",
            f"must equal execution-record sum {operation_total}",
        )
    if reported_edit_total != edit_total:
        _fail(
            "total_cost_mismatch",
            "$.applied_pixel_edit_count",
            f"must equal execution-record sum {edit_total}",
        )

    observed_changed = _require_nonnegative_int(
        root["observed_changed_pixel_count"],
        "$.observed_changed_pixel_count",
    )
    unique_planned_writes = len(_planned_write_indices(plan))
    if observed_changed > unique_planned_writes:
        _fail(
            "changed_count_out_of_range",
            "$.observed_changed_pixel_count",
            f"cannot exceed {unique_planned_writes} unique F2 planned write coordinates",
        )
    if type(root["unaffected_region_stable"]) is not bool:
        _fail(
            "invalid_type",
            "$.unaffected_region_stable",
            "must be a boolean measured against coordinates outside F2 planned writes",
        )

    _validate_qa_findings(root["qa"])
    return cast(RepairExecutionV1, value)


def execute_repair_plan(
    plan: object,
    *,
    canvas: Canvas,
    qa_evaluator: RepairQaEvaluator,
) -> RepairExecutionV1:
    """Apply only canonical F2 repairs in order, measure mutation, then rerun deterministic QA.

    The caller-owned Canvas is mutated in place. F3 takes one owned source RGBA snapshot because
    exact final delta/stability and a source digest require it. Per-repair accounting captures
    only touched coordinates, while the result digest reads the final Canvas through its
    zero-copy internal view. No provider, VLM, preview generation, or human acceptance is invoked.
    """

    validated_plan = _validated_plan(plan)
    if not isinstance(canvas, Canvas):
        _fail("invalid_canvas", "$context.canvas", "must be a tracepixel.raster.Canvas")
    if not isinstance(qa_evaluator, RepairQaEvaluator):
        _fail(
            "invalid_qa_evaluator",
            "$context.qa_evaluator",
            "must implement evaluate(canvas)",
        )

    target_canvas = validated_plan["localization"]["intake"]["target"]["canvas"]
    if canvas.width != target_canvas["width"] or canvas.height != target_canvas["height"]:
        _fail(
            "canvas_mismatch",
            "$context.canvas",
            "Canvas dimensions must exactly match the F0/F2 target canvas",
        )

    source = canvas.rgba_bytes()
    source_digest = sha256(source).hexdigest()
    executions: list[RepairExecutionItemV1] = []
    touched_union: set[int] = set()
    operation_total = 0
    edit_total = 0

    for repair in validated_plan["repairs"]:
        if repair["disposition"] == "defer":
            executions.append(
                {
                    "feedback_id": repair["feedback_id"],
                    "status": "deferred",
                    "target_stage": None,
                    "applied_operation_count": 0,
                    "applied_pixel_edit_count": 0,
                    "observed_changed_pixel_count": 0,
                }
            )
            continue

        program = repair["repair_program"]
        if program is None:
            _fail(
                "invalid_plan",
                "$.plan",
                "validated active repair unexpectedly lacked a repair program",
            )

        before, touched = _capture_touched_pixels(canvas, program)
        touched_union.update(touched)
        _apply_validated_pixel_program(canvas, program)
        changed = _count_changed_touched_pixels(canvas, before)
        operation_count, edit_count = _program_stats(program)
        operation_total += operation_count
        edit_total += edit_count
        executions.append(
            {
                "feedback_id": repair["feedback_id"],
                "status": "applied",
                "target_stage": repair["target_stage"],
                "applied_operation_count": operation_count,
                "applied_pixel_edit_count": edit_count,
                "observed_changed_pixel_count": changed,
            }
        )

    observed_changed, unaffected_region_stable = _measure_final_delta(
        source=source,
        canvas=canvas,
        touched=touched_union,
    )
    result_digest = sha256(canvas._rgba_view()).hexdigest()

    qa = _validate_qa_findings(qa_evaluator.evaluate(canvas), "$qa_evaluator.result")
    result: RepairExecutionV1 = {
        "schema": REPAIR_EXECUTION_SCHEMA_V1,
        "plan": validated_plan,
        "source_rgba_sha256": source_digest,
        "result_rgba_sha256": result_digest,
        "executions": executions,
        "applied_operation_count": operation_total,
        "applied_pixel_edit_count": edit_total,
        "observed_changed_pixel_count": observed_changed,
        "unaffected_region_stable": unaffected_region_stable,
        "qa": qa,
    }
    return validate_repair_execution(result)
