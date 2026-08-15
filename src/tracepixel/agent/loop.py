from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict, cast, runtime_checkable

from tracepixel.model import (
    ArtIntentV1,
    ArtIntentValidationError,
    PixelProgramV1,
    StageIdV1,
    validate_art_intent,
)
from tracepixel.model.execution import _apply_validated_pixel_program
from tracepixel.qa import QaFindingsV1
from tracepixel.raster import Canvas

from .observation import (
    MAX_AGENT_RECENT_REVISIONS_V1,
    AgentObservationContractError,
    AgentObservationV1,
    AgentRecentRevisionV1,
    build_agent_observation,
)
from .provider import (
    AGENT_PROVIDER_REQUEST_SCHEMA_V1,
    AgentProvider,
    AgentProviderContractError,
    AgentProviderRequestV1,
    validate_agent_provider_proposal,
    validate_agent_provider_request,
)

AGENT_LOOP_BUDGET_SCHEMA_V1 = "tracepixel.agent-loop-budget.v1"

AgentLoopStatusV1 = Literal[
    "finished",
    "iteration_budget_exhausted",
    "tool_budget_exhausted",
    "operation_budget_exhausted",
    "pixel_edit_budget_exhausted",
]


class AgentLoopBudgetV1(TypedDict):
    """Explicit finite controls for one bounded provider-neutral edit loop."""

    schema: Literal["tracepixel.agent-loop-budget.v1"]
    max_iterations: int
    max_tool_calls: int
    max_operations: int
    max_pixel_edits: int


@dataclass(frozen=True, slots=True)
class AgentPreviewFrame:
    """Optional local PNG evidence for one provider request."""

    png: bytes
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class AgentLoopResult:
    """A2 control result; complexity telemetry remains P5-A3 scope."""

    canvas: Canvas
    status: AgentLoopStatusV1
    observation: AgentObservationV1


@runtime_checkable
class AgentQaEvaluator(Protocol):
    """Provider-free deterministic QA boundary used after every accepted edit."""

    def evaluate(self, canvas: Canvas, /) -> QaFindingsV1:
        ...


@runtime_checkable
class AgentPreviewObserver(Protocol):
    """Optional bounded visual-observation source; no preview is produced by default."""

    def observe(self, canvas: Canvas, /) -> AgentPreviewFrame:
        ...


class AgentLoopContractError(ValueError):
    """Stable deterministic rejection for A2 configuration or candidate edits."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise AgentLoopContractError(code, path, message)


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


def _require_nonnegative_int(value: object, path: str) -> int:
    if type(value) is not int:
        _fail("invalid_type", path, "must be an integer")
    result = cast(int, value)
    if result < 0:
        _fail("invalid_value", path, "must be >= 0")
    return result


def _rebase(path: str, prefix: str) -> str:
    if path == "$":
        return prefix
    if path.startswith("$"):
        return f"{prefix}{path[1:]}"
    return prefix


def validate_agent_loop_budget(budget: object) -> AgentLoopBudgetV1:
    """Validate a closed A2 budget without inventing hidden defaults."""

    root = _require_exact_object(
        budget,
        "$",
        frozenset(
            (
                "schema",
                "max_iterations",
                "max_tool_calls",
                "max_operations",
                "max_pixel_edits",
            )
        ),
    )
    if root["schema"] != AGENT_LOOP_BUDGET_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"expected {AGENT_LOOP_BUDGET_SCHEMA_V1!r}",
        )
    for field in (
        "max_iterations",
        "max_tool_calls",
        "max_operations",
        "max_pixel_edits",
    ):
        _require_nonnegative_int(root[field], f"$.{field}")
    return cast(AgentLoopBudgetV1, budget)


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


def _capture_touched_pixels(canvas: Canvas, program: PixelProgramV1) -> dict[int, int]:
    """Capture only unique touched positions, never an owned full-raster snapshot."""

    rgba = canvas._rgba_view()
    width = canvas.width
    before: dict[int, int] = {}
    for operation in program["operations"]:
        for pixel in operation["pixels"]:
            index = pixel[1] * width + pixel[0]
            if index not in before:
                before[index] = _pack_at(rgba, index)
    return before


def _count_changed_pixels(canvas: Canvas, before: dict[int, int]) -> int:
    rgba = canvas._rgba_view()
    return sum(_pack_at(rgba, index) != packed for index, packed in before.items())


def _build_observation(
    *,
    canvas: Canvas,
    art_intent: ArtIntentV1,
    current_stage: StageIdV1 | None,
    revision: int,
    qa_evaluator: AgentQaEvaluator,
    recent: list[AgentRecentRevisionV1],
    preview_observer: AgentPreviewObserver | None,
) -> AgentObservationV1:
    findings = qa_evaluator.evaluate(canvas)
    try:
        observation = build_agent_observation(
            art_intent=art_intent,
            current_stage=current_stage,
            revision=revision,
            qa_findings=findings,
            recent=recent,
        )
    except AgentObservationContractError as exc:
        _fail(
            "invalid_observation",
            _rebase(exc.path, "$observation"),
            f"compact observation rejected with {exc.code}: {exc.message}",
        )

    if not observation["qa"]["findings"] or preview_observer is None:
        return observation

    frame = preview_observer.observe(canvas)
    try:
        return build_agent_observation(
            art_intent=art_intent,
            current_stage=current_stage,
            revision=revision,
            qa_findings=observation["qa"],
            recent=recent,
            preview_png=frame.png,
            preview_width=frame.width,
            preview_height=frame.height,
        )
    except AgentObservationContractError as exc:
        _fail(
            "invalid_preview_observation",
            _rebase(exc.path, "$observation"),
            f"preview observation rejected with {exc.code}: {exc.message}",
        )


def _request(instruction: str, observation: AgentObservationV1) -> AgentProviderRequestV1:
    request: AgentProviderRequestV1 = {
        "schema": AGENT_PROVIDER_REQUEST_SCHEMA_V1,
        "instruction": instruction,
        "observation": observation,
    }
    return request


def _result(
    canvas: Canvas,
    status: AgentLoopStatusV1,
    observation: AgentObservationV1,
) -> AgentLoopResult:
    return AgentLoopResult(canvas=canvas, status=status, observation=observation)


def run_bounded_edit_loop(
    provider: AgentProvider,
    *,
    canvas: Canvas,
    art_intent: object,
    instruction: str,
    qa_evaluator: AgentQaEvaluator,
    budget: object,
    current_stage: StageIdV1 | None = None,
    preview_observer: AgentPreviewObserver | None = None,
) -> AgentLoopResult:
    """Run the provider-neutral P5-A2 PixelProgram revise/finish loop.

    Every accepted provider proposal is fully validated and budget-preflighted before the
    authoritative Canvas is mutated. One ``provider.propose`` invocation consumes one A2
    tool call and one iteration. ``stage_plan`` remains a valid A0 provider proposal kind,
    but this stage-local edit loop deliberately accepts only ``pixel_program`` candidates.

    Finish is deterministic: zero selected Q5 findings means finished; any remaining finding
    means revise until an explicit budget stops the loop. No provider/model, retry policy,
    telemetry, perceptual judge, or historical transcript is introduced here.
    """

    validated_budget = validate_agent_loop_budget(budget)
    if not isinstance(canvas, Canvas):
        _fail("invalid_canvas", "$context.canvas", "must be a tracepixel.raster.Canvas")
    if not isinstance(provider, AgentProvider):
        _fail("invalid_provider", "$context.provider", "must implement AgentProvider.propose")
    if not isinstance(qa_evaluator, AgentQaEvaluator):
        _fail("invalid_qa_evaluator", "$context.qa_evaluator", "must implement evaluate(canvas)")
    if preview_observer is not None and not isinstance(preview_observer, AgentPreviewObserver):
        _fail(
            "invalid_preview_observer",
            "$context.preview_observer",
            "must implement observe(canvas)",
        )

    try:
        intent = validate_art_intent(art_intent)
    except ArtIntentValidationError as exc:
        _fail(
            "invalid_art_intent",
            _rebase(exc.path, "$context.art_intent"),
            f"ArtIntent validation failed with {exc.code}: {exc.message}",
        )
    intent = cast(ArtIntentV1, intent)
    if canvas.width != intent["canvas"]["width"] or canvas.height != intent["canvas"]["height"]:
        _fail(
            "canvas_mismatch",
            "$context.canvas",
            "Canvas dimensions must exactly match ArtIntent canvas",
        )

    revision = 0
    recent: list[AgentRecentRevisionV1] = []
    observation = _build_observation(
        canvas=canvas,
        art_intent=intent,
        current_stage=current_stage,
        revision=revision,
        qa_evaluator=qa_evaluator,
        recent=recent,
        preview_observer=preview_observer,
    )

    initial_request = _request(instruction, observation)
    try:
        validate_agent_provider_request(initial_request)
    except AgentProviderContractError as exc:
        _fail(
            "invalid_request",
            _rebase(exc.path, "$request"),
            f"provider request rejected with {exc.code}: {exc.message}",
        )

    if not observation["qa"]["findings"]:
        return _result(canvas, "finished", observation)

    iterations = 0
    tool_calls = 0
    operations = 0
    pixel_edits = 0
    request = initial_request

    while True:
        if iterations >= validated_budget["max_iterations"]:
            return _result(canvas, "iteration_budget_exhausted", observation)
        if tool_calls >= validated_budget["max_tool_calls"]:
            return _result(canvas, "tool_budget_exhausted", observation)
        if operations >= validated_budget["max_operations"]:
            return _result(canvas, "operation_budget_exhausted", observation)
        if pixel_edits >= validated_budget["max_pixel_edits"]:
            return _result(canvas, "pixel_edit_budget_exhausted", observation)

        proposal = provider.propose(request)
        iterations += 1
        tool_calls += 1

        try:
            validated_proposal = validate_agent_provider_proposal(
                proposal,
                art_intent=intent,
            )
        except AgentProviderContractError as exc:
            _fail(
                "invalid_provider_proposal",
                _rebase(exc.path, "$proposal"),
                f"provider proposal rejected with {exc.code}: {exc.message}",
            )

        if validated_proposal["kind"] != "pixel_program":
            _fail(
                "unsupported_edit_proposal",
                "$proposal.kind",
                "bounded edit loop accepts only pixel_program proposals",
            )
        program = cast(PixelProgramV1, validated_proposal["payload"])
        if program["canvas"] != intent["canvas"]:
            _fail(
                "proposal_canvas_mismatch",
                "$proposal.payload.canvas",
                "PixelProgram canvas must exactly match ArtIntent canvas",
            )

        operation_count, edit_count = _program_stats(program)
        if operations + operation_count > validated_budget["max_operations"]:
            return _result(canvas, "operation_budget_exhausted", observation)
        if pixel_edits + edit_count > validated_budget["max_pixel_edits"]:
            return _result(canvas, "pixel_edit_budget_exhausted", observation)

        source_revision = revision
        before = _capture_touched_pixels(canvas, program)
        _apply_validated_pixel_program(canvas, program)
        changed_pixels = _count_changed_pixels(canvas, before)
        operations += operation_count
        pixel_edits += edit_count
        revision += 1

        recent.append(
            {
                "revision": source_revision,
                "stage": current_stage,
                "proposal_kind": "pixel_program",
                "operation_count": operation_count,
                "changed_pixels": changed_pixels,
            }
        )
        if len(recent) > MAX_AGENT_RECENT_REVISIONS_V1:
            del recent[:-MAX_AGENT_RECENT_REVISIONS_V1]

        observation = _build_observation(
            canvas=canvas,
            art_intent=intent,
            current_stage=current_stage,
            revision=revision,
            qa_evaluator=qa_evaluator,
            recent=recent,
            preview_observer=preview_observer,
        )
        if not observation["qa"]["findings"]:
            return _result(canvas, "finished", observation)
        request = _request(instruction, observation)
