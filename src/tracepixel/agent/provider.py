from __future__ import annotations

from math import isfinite
from typing import Literal, Protocol, TypeAlias, TypedDict, cast, runtime_checkable

from tracepixel.model import (
    PixelProgramV1,
    PixelProgramValidationError,
    StagePipelineValidationError,
    StagePlanV1,
    validate_pixel_program,
    validate_stage_plan,
)

from .observation import (
    AgentObservationContractError,
    AgentObservationV1,
    validate_agent_observation,
)

AGENT_PROVIDER_REQUEST_SCHEMA_V1 = "tracepixel.agent-provider-request.v1"
AGENT_PROVIDER_PROPOSAL_SCHEMA_V1 = "tracepixel.agent-provider-proposal.v1"

AgentProposalKindV1 = Literal["pixel_program", "stage_plan"]
JsonValueV1: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["JsonValueV1"]
    | dict[str, "JsonValueV1"]
)


class AgentProviderRequestV1(TypedDict):
    """Provider-neutral request carrying one bounded P5-A1 observation."""

    schema: Literal["tracepixel.agent-provider-request.v1"]
    instruction: str
    observation: AgentObservationV1


class PixelProgramProposalV1(TypedDict):
    """Provider proposal carrying candidate PixelProgram data, not raster authority."""

    schema: Literal["tracepixel.agent-provider-proposal.v1"]
    kind: Literal["pixel_program"]
    payload: PixelProgramV1


class StagePlanProposalV1(TypedDict):
    """Provider proposal carrying candidate staged-authoring data."""

    schema: Literal["tracepixel.agent-provider-proposal.v1"]
    kind: Literal["stage_plan"]
    payload: StagePlanV1


AgentProviderProposalV1: TypeAlias = PixelProgramProposalV1 | StagePlanProposalV1


@runtime_checkable
class AgentProvider(Protocol):
    """Minimal replaceable provider seam; adapters keep SDK/network state outside core."""

    def propose(
        self,
        request: AgentProviderRequestV1,
        /,
    ) -> AgentProviderProposalV1:
        ...


class AgentProviderContractError(ValueError):
    """Stable deterministic rejection for provider-neutral request/proposal envelopes."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise AgentProviderContractError(code, path, message)


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


def _validate_json_value(value: object, path: str) -> None:
    value_type = type(value)
    if value is None or value_type in (str, bool, int):
        return
    if value_type is float:
        if not isfinite(cast(float, value)):
            _fail("invalid_json_value", path, "JSON numbers must be finite")
        return
    if value_type is list:
        for index, item in enumerate(cast(list[object], value)):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if value_type is dict:
        obj = cast(dict[object, object], value)
        for key, item in obj.items():
            if type(key) is not str:
                _fail("invalid_json_value", path, "JSON object keys must be strings")
            _validate_json_value(item, f"{path}[{key!r}]")
        return
    _fail(
        "invalid_json_value",
        path,
        "must contain only JSON-compatible null/bool/number/string/array/object values",
    )


def _validate_schema(value: object, *, path: str, expected: str) -> None:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    if value != expected:
        _fail(
            "unsupported_schema",
            path,
            f"unsupported schema {value!r}; expected {expected!r}",
        )


def _rebase_payload_path(path: str) -> str:
    if path == "$":
        return "$.payload"
    if path.startswith("$"):
        return f"$.payload{path[1:]}"
    return "$.payload"


def _rebase_observation_path(path: str) -> str:
    if path == "$":
        return "$.observation"
    if path.startswith("$"):
        return f"$.observation{path[1:]}"
    return "$.observation"


def validate_agent_provider_request(request: object) -> AgentProviderRequestV1:
    """Validate the provider-neutral request and its bounded P5-A1 observation."""

    root = _require_exact_object(
        request,
        "$",
        frozenset(("schema", "instruction", "observation")),
    )
    _validate_schema(
        root["schema"],
        path="$.schema",
        expected=AGENT_PROVIDER_REQUEST_SCHEMA_V1,
    )

    instruction = root["instruction"]
    if type(instruction) is not str:
        _fail("invalid_type", "$.instruction", "must be a string")
    if not cast(str, instruction).strip():
        _fail("invalid_instruction", "$.instruction", "must not be blank")

    observation = root["observation"]
    if type(observation) is not dict:
        _fail("invalid_type", "$.observation", "must be a JSON object")
    _validate_json_value(observation, "$.observation")
    try:
        validate_agent_observation(observation)
    except AgentObservationContractError as exc:
        _fail(
            "invalid_observation",
            _rebase_observation_path(exc.path),
            f"AgentObservation validator rejected with {exc.code}: {exc.message}",
        )
    return cast(AgentProviderRequestV1, request)


def validate_agent_provider_proposal(
    proposal: object,
    *,
    art_intent: object | None = None,
) -> AgentProviderProposalV1:
    """Validate provider output, delegating payload authority to existing P2/P3 validators."""

    root = _require_exact_object(
        proposal,
        "$",
        frozenset(("schema", "kind", "payload")),
    )
    _validate_schema(
        root["schema"],
        path="$.schema",
        expected=AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
    )

    kind = root["kind"]
    if type(kind) is not str:
        _fail("invalid_type", "$.kind", "must be a string")
    if kind not in ("pixel_program", "stage_plan"):
        _fail(
            "unsupported_proposal_kind",
            "$.kind",
            "must be 'pixel_program' or 'stage_plan'",
        )

    try:
        if kind == "pixel_program":
            validate_pixel_program(root["payload"])
        else:
            if art_intent is None:
                _fail(
                    "missing_validation_context",
                    "$context.art_intent",
                    "stage_plan proposals require ArtIntent validation context",
                )
            validate_stage_plan(root["payload"], art_intent=art_intent)
    except PixelProgramValidationError as exc:
        _fail(
            "invalid_proposal_payload",
            _rebase_payload_path(exc.path),
            f"PixelProgram validator rejected with {exc.code}: {exc.message}",
        )
    except StagePipelineValidationError as exc:
        _fail(
            "invalid_proposal_payload",
            _rebase_payload_path(exc.path),
            f"StagePlan validator rejected with {exc.code}: {exc.message}",
        )

    return cast(AgentProviderProposalV1, proposal)
