from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Literal, Protocol, TypedDict, cast, runtime_checkable

from tracepixel.model import StageIdV1
from tracepixel.qa import QaFindingsV1
from tracepixel.raster import Canvas

from .loop import (
    AgentLoopContractError,
    AgentLoopResult,
    AgentLoopStatusV1,
    AgentPreviewFrame,
    AgentPreviewObserver,
    AgentQaEvaluator,
    run_bounded_edit_loop,
)
from .provider import AgentProvider, AgentProviderProposalV1, AgentProviderRequestV1

AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1 = "tracepixel.agent-complexity-telemetry.v1"


class AgentComplexityTelemetryV1(TypedDict):
    """Machine-readable P5-A3 complexity evidence; never raster or Pixel IR authority."""

    schema: Literal["tracepixel.agent-complexity-telemetry.v1"]
    input_tokens: int | None
    output_tokens: int | None
    tool_calls: int
    operation_calls: int
    exposed_concept_count: int
    visual_observation_calls: int
    iterations: int
    revisions: int
    changed_pixels: int
    wall_time_ns: int
    api_cost_usd_micros: int | None
    human_interventions: int
    failure_category: str | None


@dataclass(frozen=True, slots=True)
class AgentProviderUsage:
    """Optional provider-neutral usage sample for exactly one completed provider call."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    api_cost_usd_micros: int | None = None

    def __post_init__(self) -> None:
        for name in ("input_tokens", "output_tokens", "api_cost_usd_micros"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None")


@runtime_checkable
class AgentProviderUsageSource(Protocol):
    """Optional adapter hook; absence never blocks provider-neutral orchestration."""

    def last_usage(self, /) -> AgentProviderUsage | None:
        ...


@dataclass(frozen=True, slots=True)
class AgentMeasuredLoopResult:
    """A2 loop result paired with non-authoritative A3 complexity evidence."""

    loop: AgentLoopResult
    telemetry: AgentComplexityTelemetryV1


class AgentMeasuredLoopError(RuntimeError):
    """A2 deterministic failure paired with the complexity evidence observed so far."""

    def __init__(
        self,
        cause: AgentLoopContractError,
        telemetry: AgentComplexityTelemetryV1,
    ) -> None:
        self.cause = cause
        self.telemetry = telemetry
        super().__init__(str(cause))


class AgentTelemetryContractError(ValueError):
    """Stable rejection for serialized telemetry values or wrapper-only inputs."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise AgentTelemetryContractError(code, path, message)


def _require_nonnegative_int(value: object, path: str) -> int:
    if type(value) is not int:
        _fail("invalid_type", path, "must be an integer")
    result = cast(int, value)
    if result < 0:
        _fail("invalid_value", path, "must be >= 0")
    return result


def _validate_optional_nonnegative_int(value: object, path: str) -> None:
    if value is None:
        return
    _require_nonnegative_int(value, path)


def validate_agent_complexity_telemetry(value: object) -> AgentComplexityTelemetryV1:
    """Validate the closed A3 evidence envelope without making it execution authority."""

    if type(value) is not dict:
        _fail("invalid_type", "$", "must be a JSON object")
    root = cast(dict[object, object], value)
    if not all(type(key) is str for key in root):
        _fail("invalid_fields", "$", "object keys must be strings")
    typed = cast(dict[str, object], root)
    fields = frozenset(
        (
            "schema",
            "input_tokens",
            "output_tokens",
            "tool_calls",
            "operation_calls",
            "exposed_concept_count",
            "visual_observation_calls",
            "iterations",
            "revisions",
            "changed_pixels",
            "wall_time_ns",
            "api_cost_usd_micros",
            "human_interventions",
            "failure_category",
        )
    )
    actual = frozenset(typed)
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail("invalid_fields", "$", "; ".join(parts))
    if typed["schema"] != AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"expected {AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1!r}",
        )
    _validate_optional_nonnegative_int(typed["input_tokens"], "$.input_tokens")
    _validate_optional_nonnegative_int(typed["output_tokens"], "$.output_tokens")
    for field in (
        "tool_calls",
        "operation_calls",
        "exposed_concept_count",
        "visual_observation_calls",
        "iterations",
        "revisions",
        "changed_pixels",
        "wall_time_ns",
        "human_interventions",
    ):
        _require_nonnegative_int(typed[field], f"$.{field}")
    _validate_optional_nonnegative_int(
        typed["api_cost_usd_micros"],
        "$.api_cost_usd_micros",
    )
    failure = typed["failure_category"]
    if failure is not None:
        if type(failure) is not str:
            _fail("invalid_type", "$.failure_category", "must be a string or null")
        text = cast(str, failure)
        if not text or any(
            not (("a" <= character <= "z") or ("0" <= character <= "9") or character in "_.-")
            for character in text
        ):
            _fail(
                "invalid_value",
                "$.failure_category",
                "must contain only lowercase ASCII letters, digits, '_', '.', or '-'",
            )
    return cast(AgentComplexityTelemetryV1, value)


def _pack_at(rgba: memoryview, pixel_index: int) -> int:
    offset = pixel_index << 2
    return (
        (rgba[offset] << 24)
        | (rgba[offset + 1] << 16)
        | (rgba[offset + 2] << 8)
        | rgba[offset + 3]
    )


@dataclass(slots=True)
class _PendingEdit:
    operation_count: int
    before: dict[int, int]


class _UsageTotals:
    def __init__(self) -> None:
        self.calls = 0
        self.input_total = 0
        self.output_total = 0
        self.cost_total = 0
        self.input_complete = True
        self.output_complete = True
        self.cost_complete = True

    def add(self, usage: AgentProviderUsage | None) -> None:
        self.calls += 1
        if usage is None:
            self.input_complete = False
            self.output_complete = False
            self.cost_complete = False
            return
        if usage.input_tokens is None:
            self.input_complete = False
        else:
            self.input_total += usage.input_tokens
        if usage.output_tokens is None:
            self.output_complete = False
        else:
            self.output_total += usage.output_tokens
        if usage.api_cost_usd_micros is None:
            self.cost_complete = False
        else:
            self.cost_total += usage.api_cost_usd_micros

    def input_tokens(self) -> int | None:
        return self.input_total if self.input_complete else None

    def output_tokens(self) -> int | None:
        return self.output_total if self.output_complete else None

    def api_cost_usd_micros(self) -> int | None:
        return self.cost_total if self.cost_complete else None


def _collect_concepts(value: object, path: str, concepts: set[str]) -> None:
    if type(value) is dict:
        for key, child in cast(dict[object, object], value).items():
            if type(key) is not str or key == "schema":
                continue
            child_path = f"{path}.{key}"
            concepts.add(child_path)
            _collect_concepts(child, child_path, concepts)
        return
    if type(value) is list:
        item_path = f"{path}[]"
        for child in cast(list[object], value):
            _collect_concepts(child, item_path, concepts)


def _pending_edit(canvas: Canvas, proposal: object) -> _PendingEdit | None:
    if type(proposal) is not dict:
        return None
    root = cast(dict[object, object], proposal)
    if root.get("kind") != "pixel_program":
        return None
    payload = root.get("payload")
    if type(payload) is not dict:
        return None
    operations = cast(dict[object, object], payload).get("operations")
    if type(operations) is not list:
        return None

    rgba = canvas._rgba_view()
    width = canvas.width
    before: dict[int, int] = {}
    for operation in cast(list[object], operations):
        if type(operation) is not dict:
            return None
        pixels = cast(dict[object, object], operation).get("pixels")
        if type(pixels) is not list:
            return None
        for pixel in cast(list[object], pixels):
            if type(pixel) is not list or len(cast(list[object], pixel)) < 2:
                return None
            x, y = cast(list[object], pixel)[:2]
            if type(x) is not int or type(y) is not int:
                return None
            if x < 0 or y < 0 or x >= canvas.width or y >= canvas.height:
                return None
            index = y * width + x
            if index not in before:
                before[index] = _pack_at(rgba, index)
    return _PendingEdit(operation_count=len(cast(list[object], operations)), before=before)


class _MeasuredProvider:
    def __init__(self, provider: AgentProvider, canvas: Canvas) -> None:
        self.provider = provider
        self.canvas = canvas
        self.tool_calls = 0
        self.iterations = 0
        self.operation_calls = 0
        self.revisions = 0
        self.changed_pixels = 0
        self.concepts: set[str] = set()
        self.usage = _UsageTotals()
        self.pending: _PendingEdit | None = None

    def propose(self, request: AgentProviderRequestV1, /) -> AgentProviderProposalV1:
        self.tool_calls += 1
        self.iterations += 1
        _collect_concepts(request, "$request", self.concepts)
        proposal = self.provider.propose(request)

        usage: AgentProviderUsage | None = None
        if isinstance(self.provider, AgentProviderUsageSource):
            candidate = self.provider.last_usage()
            if isinstance(candidate, AgentProviderUsage):
                usage = candidate
        self.usage.add(usage)
        self.pending = _pending_edit(self.canvas, proposal)
        return proposal

    def complete_revision(self) -> None:
        pending = self.pending
        if pending is None:
            return
        rgba = self.canvas._rgba_view()
        self.operation_calls += pending.operation_count
        self.revisions += 1
        self.changed_pixels += sum(
            _pack_at(rgba, index) != packed
            for index, packed in pending.before.items()
        )
        self.pending = None


class _MeasuredQa:
    def __init__(self, qa: AgentQaEvaluator, provider: _MeasuredProvider) -> None:
        self.qa = qa
        self.provider = provider

    def evaluate(self, canvas: Canvas, /) -> QaFindingsV1:
        findings = self.qa.evaluate(canvas)
        self.provider.complete_revision()
        return findings


class _MeasuredPreview:
    def __init__(self, preview: AgentPreviewObserver) -> None:
        self.preview = preview
        self.calls = 0

    def observe(self, canvas: Canvas, /) -> AgentPreviewFrame:
        self.calls += 1
        return self.preview.observe(canvas)


def _failure_for_status(status: AgentLoopStatusV1) -> str | None:
    return {
        "finished": None,
        "iteration_budget_exhausted": "budget.iteration",
        "tool_budget_exhausted": "budget.tool",
        "operation_budget_exhausted": "budget.operation",
        "pixel_edit_budget_exhausted": "budget.pixel_edit",
    }[status]


def _build_telemetry(
    measured_provider: _MeasuredProvider | None,
    measured_preview: _MeasuredPreview | None,
    *,
    wall_time_ns: int,
    human_interventions: int,
    failure_category: str | None,
) -> AgentComplexityTelemetryV1:
    if measured_provider is None:
        input_tokens: int | None = 0
        output_tokens: int | None = 0
        api_cost: int | None = 0
        tool_calls = 0
        operation_calls = 0
        exposed_concepts = 0
        iterations = 0
        revisions = 0
        changed_pixels = 0
    else:
        input_tokens = measured_provider.usage.input_tokens()
        output_tokens = measured_provider.usage.output_tokens()
        api_cost = measured_provider.usage.api_cost_usd_micros()
        tool_calls = measured_provider.tool_calls
        operation_calls = measured_provider.operation_calls
        exposed_concepts = len(measured_provider.concepts)
        iterations = measured_provider.iterations
        revisions = measured_provider.revisions
        changed_pixels = measured_provider.changed_pixels

    telemetry: AgentComplexityTelemetryV1 = {
        "schema": AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tool_calls": tool_calls,
        "operation_calls": operation_calls,
        "exposed_concept_count": exposed_concepts,
        "visual_observation_calls": 0 if measured_preview is None else measured_preview.calls,
        "iterations": iterations,
        "revisions": revisions,
        "changed_pixels": changed_pixels,
        "wall_time_ns": wall_time_ns,
        "api_cost_usd_micros": api_cost,
        "human_interventions": human_interventions,
        "failure_category": failure_category,
    }
    return validate_agent_complexity_telemetry(telemetry)


def run_bounded_edit_loop_with_telemetry(
    provider: AgentProvider,
    *,
    canvas: Canvas,
    art_intent: object,
    instruction: str,
    qa_evaluator: AgentQaEvaluator,
    budget: object,
    current_stage: StageIdV1 | None = None,
    preview_observer: AgentPreviewObserver | None = None,
    human_interventions: int = 0,
) -> AgentMeasuredLoopResult:
    """Run the A2 loop while collecting A3 evidence without changing A2 authority.

    Provider token/cost totals are exact only when every completed provider call exposes an
    ``AgentProviderUsage`` sample. If any call omits a metric, that aggregate is ``None``.
    Wall time is observational evidence and is intentionally not deterministic correctness.
    """

    _require_nonnegative_int(human_interventions, "$telemetry.human_interventions")

    measured_provider: _MeasuredProvider | None = None
    measured_qa: AgentQaEvaluator = qa_evaluator
    if isinstance(provider, AgentProvider) and isinstance(canvas, Canvas):
        measured_provider = _MeasuredProvider(provider, canvas)
        if isinstance(qa_evaluator, AgentQaEvaluator):
            measured_qa = _MeasuredQa(qa_evaluator, measured_provider)

    measured_preview: _MeasuredPreview | None = None
    delegated_preview = preview_observer
    if preview_observer is not None and isinstance(preview_observer, AgentPreviewObserver):
        measured_preview = _MeasuredPreview(preview_observer)
        delegated_preview = measured_preview

    delegated_provider = provider if measured_provider is None else measured_provider
    started = perf_counter_ns()
    try:
        loop = run_bounded_edit_loop(
            delegated_provider,
            canvas=canvas,
            art_intent=art_intent,
            instruction=instruction,
            qa_evaluator=measured_qa,
            budget=budget,
            current_stage=current_stage,
            preview_observer=delegated_preview,
        )
    except AgentLoopContractError as exc:
        telemetry = _build_telemetry(
            measured_provider,
            measured_preview,
            wall_time_ns=max(0, perf_counter_ns() - started),
            human_interventions=human_interventions,
            failure_category=f"contract.{exc.code}",
        )
        raise AgentMeasuredLoopError(exc, telemetry) from exc

    telemetry = _build_telemetry(
        measured_provider,
        measured_preview,
        wall_time_ns=max(0, perf_counter_ns() - started),
        human_interventions=human_interventions,
        failure_category=_failure_for_status(loop.status),
    )
    return AgentMeasuredLoopResult(loop=loop, telemetry=telemetry)
