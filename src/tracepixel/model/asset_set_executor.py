from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from threading import Lock
from time import perf_counter_ns
from typing import Literal, Protocol, cast, runtime_checkable

from .asset_set_execution import (
    ASSET_SET_EXECUTION_REPORT_SCHEMA_V1,
    ASSET_SET_MEMBER_EXECUTION_SCHEMA_V1,
    AssetSetBudgetDimensionV1,
    AssetSetExecutionReportV1,
    AssetSetMemberCacheV1,
    AssetSetMemberEvidenceRefsV1,
    AssetSetMemberExecutionV1,
)
from .asset_set_schedule import AssetRequestV1, AssetSetScheduleV1
from .asset_set_schedule_validation import validate_asset_set_schedule


class AssetSetExecutionContractError(ValueError):
    """Stable P8-B1 runtime contract failure."""


class AssetSetBudgetExhausted(RuntimeError):
    """Raised before a member operation that would knowingly exceed a shared batch budget."""

    def __init__(self, dimension: AssetSetBudgetDimensionV1) -> None:
        self.dimension = dimension
        super().__init__(f"asset-set aggregate {dimension} budget exhausted")


@dataclass(frozen=True, slots=True)
class SingleAssetExecutionOutput:
    """Retained non-raster outcome produced by the authoritative single-asset path."""

    status: Literal["succeeded", "failed"]
    result_ref: str | None = None
    result_sha256: str | None = None
    cache_decision: Literal["executed", "reused"] = "executed"
    source_request_sha256: str | None = None
    source_result_ref: str | None = None
    source_result_sha256: str | None = None
    deterministic_qa_ref: str | None = None
    perceptual_ref: str | None = None
    complexity_ref: str | None = None
    provenance_ref: str | None = None
    failure_category: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ("succeeded", "failed"):
            raise AssetSetExecutionContractError("status must be 'succeeded' or 'failed'")
        if self.cache_decision not in ("executed", "reused"):
            raise AssetSetExecutionContractError("cache_decision must be 'executed' or 'reused'")
        if self.status == "succeeded":
            if not self.result_ref or not _is_sha256(self.result_sha256):
                raise AssetSetExecutionContractError(
                    "successful single-asset execution requires result_ref and lowercase SHA-256"
                )
            if self.failure_category is not None or self.failure_reason is not None:
                raise AssetSetExecutionContractError(
                    "successful single-asset execution cannot carry failure fields"
                )
        else:
            if self.result_ref is not None or self.result_sha256 is not None:
                raise AssetSetExecutionContractError(
                    "failed single-asset execution cannot claim a retained result identity"
                )
            if not self.failure_category or not self.failure_reason:
                raise AssetSetExecutionContractError(
                    "failed single-asset execution requires failure_category and failure_reason"
                )

        if self.cache_decision == "reused":
            if self.status != "succeeded":
                raise AssetSetExecutionContractError("only successful members may reuse a retained result")
            if (
                not _is_sha256(self.source_request_sha256)
                or not self.source_result_ref
                or not _is_sha256(self.source_result_sha256)
            ):
                raise AssetSetExecutionContractError(
                    "reused result requires immutable source request/result identities"
                )
        elif any(
            value is not None
            for value in (
                self.source_request_sha256,
                self.source_result_ref,
                self.source_result_sha256,
            )
        ):
            raise AssetSetExecutionContractError(
                "executed result cannot carry cache source identities"
            )

        for value in (
            self.deterministic_qa_ref,
            self.perceptual_ref,
            self.complexity_ref,
            self.provenance_ref,
        ):
            if value is not None and (type(value) is not str or not value):
                raise AssetSetExecutionContractError("evidence refs must be non-empty strings or None")


@runtime_checkable
class SingleAssetExecutor(Protocol):
    """Adapter around the existing single-asset pipeline.

    Implementations may be called concurrently. Every provider call and pixel-edit batch must
    claim the shared P8-B1 context before performing the operation, and every completed provider
    call must report exact input/output tokens to the same context.
    """

    def execute(
        self,
        request: AssetRequestV1,
        /,
        *,
        member_id: str,
        request_sha256: str,
        context: AssetSetMemberExecutionContext,
    ) -> SingleAssetExecutionOutput:
        ...


class _AggregateBudgetState:
    def __init__(self, schedule: AssetSetScheduleV1, start_ns: int) -> None:
        self.max_provider_calls = schedule["aggregate_budget"]["max_provider_calls"]
        self.max_pixel_edits = schedule["aggregate_budget"]["max_pixel_edits"]
        self.max_wall_time_ns = schedule["aggregate_budget"]["max_wall_time_ms"] * 1_000_000
        self.start_ns = start_ns
        self.provider_calls = 0
        self.pixel_edits = 0
        self.exhausted: set[AssetSetBudgetDimensionV1] = set()
        self._lock = Lock()

    def _check_wall_locked(self, now_ns: int) -> None:
        if now_ns - self.start_ns >= self.max_wall_time_ns:
            self.exhausted.add("wall_time")
            raise AssetSetBudgetExhausted("wall_time")

    def check_wall(self) -> None:
        with self._lock:
            self._check_wall_locked(perf_counter_ns())

    def reserve_provider_call(self) -> None:
        with self._lock:
            self._check_wall_locked(perf_counter_ns())
            if self.provider_calls >= self.max_provider_calls:
                self.exhausted.add("provider_calls")
                raise AssetSetBudgetExhausted("provider_calls")
            self.provider_calls += 1

    def reserve_pixel_edits(self, count: int) -> None:
        with self._lock:
            self._check_wall_locked(perf_counter_ns())
            if self.pixel_edits + count > self.max_pixel_edits:
                self.exhausted.add("pixel_edits")
                raise AssetSetBudgetExhausted("pixel_edits")
            self.pixel_edits += count

    def exhausted_dimensions(self) -> list[AssetSetBudgetDimensionV1]:
        order: tuple[AssetSetBudgetDimensionV1, ...] = (
            "provider_calls",
            "pixel_edits",
            "wall_time",
        )
        with self._lock:
            return [dimension for dimension in order if dimension in self.exhausted]


class AssetSetMemberExecutionContext:
    """Per-member accounting view backed by one thread-safe aggregate budget authority."""

    __slots__ = (
        "_budget",
        "_provider_calls",
        "_input_tokens",
        "_output_tokens",
        "_token_accounting_complete",
        "_pixel_edits",
        "_open_provider_calls",
        "_retry_reasons",
        "_repair_reasons",
    )

    def __init__(self, budget: _AggregateBudgetState) -> None:
        self._budget = budget
        self._provider_calls = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._token_accounting_complete = True
        self._pixel_edits = 0
        self._open_provider_calls = 0
        self._retry_reasons: list[str] = []
        self._repair_reasons: list[str] = []

    def check_wall_time(self) -> None:
        self._budget.check_wall()

    def before_provider_call(self) -> None:
        """Reserve one aggregate provider call before invoking the provider."""

        self._budget.reserve_provider_call()
        self._provider_calls += 1
        self._open_provider_calls += 1

    def after_provider_call(self, *, input_tokens: int, output_tokens: int) -> None:
        """Attribute exact provider-reported tokens for one previously reserved call."""

        _nonnegative_int(input_tokens, "input_tokens")
        _nonnegative_int(output_tokens, "output_tokens")
        if self._open_provider_calls <= 0:
            raise AssetSetExecutionContractError(
                "after_provider_call requires one unmatched before_provider_call"
            )
        self._open_provider_calls -= 1
        self._input_tokens += input_tokens
        self._output_tokens += output_tokens

    def before_pixel_edits(self, count: int) -> None:
        """Reserve a known pixel-edit count before mutating the member raster."""

        _nonnegative_int(count, "pixel_edits")
        self._budget.reserve_pixel_edits(count)
        self._pixel_edits += count

    def record_retry(self, reason: str) -> None:
        self._retry_reasons.append(_reason(reason, "retry reason"))

    def record_repair(self, reason: str) -> None:
        self._repair_reasons.append(_reason(reason, "repair reason"))

    def _mark_incomplete_provider_usage(self) -> None:
        if self._open_provider_calls:
            self._token_accounting_complete = False
            self._open_provider_calls = 0

    def _finish(self) -> None:
        if self._open_provider_calls:
            self._mark_incomplete_provider_usage()
            raise AssetSetExecutionContractError(
                "every started provider call must report exact token usage before member completion"
            )


class _RuntimeState:
    def __init__(self) -> None:
        self.live = 0
        self.peak = 0
        self._lock = Lock()

    def start_member(self) -> None:
        with self._lock:
            self.live += 1
            self.peak = max(self.peak, self.live)

    def finish_member(self) -> None:
        with self._lock:
            self.live -= 1


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(cast(str, value)) == 64
        and all(character in "0123456789abcdef" for character in cast(str, value))
    )


def _nonnegative_int(value: object, name: str) -> int:
    if type(value) is not int or cast(int, value) < 0:
        raise AssetSetExecutionContractError(f"{name} must be a non-negative integer")
    return cast(int, value)


def _reason(value: object, name: str) -> str:
    if type(value) is not str or not cast(str, value) or len(cast(str, value)) > 256:
        raise AssetSetExecutionContractError(f"{name} must be a non-empty string of length <= 256")
    return cast(str, value)


def _cache(output: SingleAssetExecutionOutput) -> AssetSetMemberCacheV1:
    return {
        "decision": output.cache_decision,
        "source_request_sha256": output.source_request_sha256,
        "source_result_ref": output.source_result_ref,
        "source_result_sha256": output.source_result_sha256,
    }


def _evidence(output: SingleAssetExecutionOutput) -> AssetSetMemberEvidenceRefsV1:
    return {
        "deterministic_qa_ref": output.deterministic_qa_ref,
        "perceptual_ref": output.perceptual_ref,
        "complexity_ref": output.complexity_ref,
        "provenance_ref": output.provenance_ref,
    }


def _member_record(
    member: dict[str, object],
    *,
    status: Literal["succeeded", "failed", "budget_exhausted"],
    context: AssetSetMemberExecutionContext,
    wall_time_ns: int,
    output: SingleAssetExecutionOutput | None,
    failure_category: str | None = None,
    failure_reason: str | None = None,
) -> AssetSetMemberExecutionV1:
    if output is None:
        cache: AssetSetMemberCacheV1 = {
            "decision": "executed",
            "source_request_sha256": None,
            "source_result_ref": None,
            "source_result_sha256": None,
        }
        evidence: AssetSetMemberEvidenceRefsV1 = {
            "deterministic_qa_ref": None,
            "perceptual_ref": None,
            "complexity_ref": None,
            "provenance_ref": None,
        }
        result_ref = None
        result_sha256 = None
    else:
        cache = _cache(output)
        evidence = _evidence(output)
        result_ref = output.result_ref
        result_sha256 = output.result_sha256
        if failure_category is None:
            failure_category = output.failure_category
        if failure_reason is None:
            failure_reason = output.failure_reason

    return {
        "schema": ASSET_SET_MEMBER_EXECUTION_SCHEMA_V1,
        "ordinal": cast(int, member["ordinal"]),
        "member_id": cast(str, member["member_id"]),
        "request_ref": cast(str, member["request_ref"]),
        "request_sha256": cast(str, member["request_sha256"]),
        "status": status,
        "result_ref": result_ref,
        "result_sha256": result_sha256,
        "provider_calls": context._provider_calls,
        "input_tokens": context._input_tokens if context._token_accounting_complete else None,
        "output_tokens": context._output_tokens if context._token_accounting_complete else None,
        "token_accounting_complete": context._token_accounting_complete,
        "pixel_edits": context._pixel_edits,
        "retry_count": len(context._retry_reasons),
        "retry_reasons": list(context._retry_reasons),
        "repair_count": len(context._repair_reasons),
        "repair_reasons": list(context._repair_reasons),
        "cache": cache,
        "wall_time_ns": wall_time_ns,
        "evidence_refs": evidence,
        "failure_category": failure_category,
        "failure_reason": failure_reason,
    }


def _run_member(
    *,
    member: dict[str, object],
    request: AssetRequestV1,
    executor: SingleAssetExecutor,
    budget: _AggregateBudgetState,
    runtime: _RuntimeState,
) -> AssetSetMemberExecutionV1:
    context = AssetSetMemberExecutionContext(budget)
    started = perf_counter_ns()
    runtime.start_member()
    try:
        output = executor.execute(
            request,
            member_id=cast(str, member["member_id"]),
            request_sha256=cast(str, member["request_sha256"]),
            context=context,
        )
        if not isinstance(output, SingleAssetExecutionOutput):
            raise AssetSetExecutionContractError(
                "single-asset executor must return SingleAssetExecutionOutput"
            )
        context._finish()
        status: Literal["succeeded", "failed"] = output.status
        return _member_record(
            member,
            status=status,
            context=context,
            wall_time_ns=perf_counter_ns() - started,
            output=output,
        )
    except AssetSetBudgetExhausted as exc:
        context._mark_incomplete_provider_usage()
        return _member_record(
            member,
            status="budget_exhausted",
            context=context,
            wall_time_ns=perf_counter_ns() - started,
            output=None,
            failure_category=f"budget.{exc.dimension}",
            failure_reason="aggregate budget denied the next member operation",
        )
    except Exception as exc:
        context._mark_incomplete_provider_usage()
        return _member_record(
            member,
            status="failed",
            context=context,
            wall_time_ns=perf_counter_ns() - started,
            output=None,
            failure_category="executor.exception",
            failure_reason=type(exc).__name__,
        )
    finally:
        runtime.finish_member()


def _not_admitted(
    member: dict[str, object],
    dimension: AssetSetBudgetDimensionV1,
    budget: _AggregateBudgetState,
) -> AssetSetMemberExecutionV1:
    context = AssetSetMemberExecutionContext(budget)
    return _member_record(
        member,
        status="budget_exhausted",
        context=context,
        wall_time_ns=0,
        output=None,
        failure_category=f"budget.{dimension}",
        failure_reason="member was not admitted because the aggregate budget was exhausted",
    )


def execute_asset_set_schedule(
    schedule: object,
    request_set: object,
    asset_set: object,
    request_payloads: dict[str, object],
    executor: SingleAssetExecutor,
) -> AssetSetExecutionReportV1:
    """Execute one validated P8-B0 schedule with isolated member state and exact accounting."""

    batch_started = perf_counter_ns()
    scheduler_wall_time_ns = 0

    timer = perf_counter_ns()
    validated = validate_asset_set_schedule(schedule, request_set, asset_set, request_payloads)
    scheduler_wall_time_ns += perf_counter_ns() - timer
    if not isinstance(executor, SingleAssetExecutor):
        raise AssetSetExecutionContractError(
            "executor must implement the concurrent-safe SingleAssetExecutor protocol"
        )

    members = cast(list[dict[str, object]], validated["members"])
    budget = _AggregateBudgetState(validated, batch_started)
    runtime = _RuntimeState()
    retained: list[AssetSetMemberExecutionV1 | None] = [None] * len(members)

    next_index = 0
    futures: dict[Future[AssetSetMemberExecutionV1], int] = {}
    max_workers = validated["max_concurrency"]

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tracepixel-asset-set") as pool:
        while next_index < len(members) or futures:
            timer = perf_counter_ns()
            while next_index < len(members) and len(futures) < max_workers:
                try:
                    budget.check_wall()
                except AssetSetBudgetExhausted:
                    break
                member = members[next_index]
                request = cast(AssetRequestV1, request_payloads[cast(str, member["request_ref"])])
                future = pool.submit(
                    _run_member,
                    member=member,
                    request=request,
                    executor=executor,
                    budget=budget,
                    runtime=runtime,
                )
                futures[future] = next_index
                next_index += 1
            scheduler_wall_time_ns += perf_counter_ns() - timer

            if not futures:
                break

            waited_started = perf_counter_ns()
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            waited_ns = perf_counter_ns() - waited_started

            timer = perf_counter_ns()
            for future in done:
                index = futures.pop(future)
                retained[index] = future.result()
            scheduler_wall_time_ns += max(0, perf_counter_ns() - timer)
            _ = waited_ns  # explicitly excluded from scheduler overhead

    if next_index < len(members):
        exhausted = budget.exhausted_dimensions()
        dimension: AssetSetBudgetDimensionV1 = "wall_time" if "wall_time" in exhausted else "wall_time"
        for index in range(next_index, len(members)):
            retained[index] = _not_admitted(members[index], dimension, budget)

    complete = cast(list[AssetSetMemberExecutionV1], retained)
    if any(member is None for member in retained):
        raise AssetSetExecutionContractError("internal error: every scheduled member must be retained")

    batch_wall_time_ns = perf_counter_ns() - batch_started
    failed_member_ids = [
        member["member_id"]
        for member in complete
        if member["status"] != "succeeded"
    ]
    token_accounting_complete = all(
        member["token_accounting_complete"] for member in complete
    )
    aggregate_input_tokens = (
        sum(cast(int, member["input_tokens"]) for member in complete)
        if token_accounting_complete
        else None
    )
    aggregate_output_tokens = (
        sum(cast(int, member["output_tokens"]) for member in complete)
        if token_accounting_complete
        else None
    )

    report: AssetSetExecutionReportV1 = {
        "schema": ASSET_SET_EXECUTION_REPORT_SCHEMA_V1,
        "asset_set_id": validated["asset_set_id"],
        "asset_set_sha256": validated["asset_set_sha256"],
        "request_sha256": validated["request_sha256"],
        "declared_max_concurrency": validated["max_concurrency"],
        "observed_peak_live_members": runtime.peak,
        "aggregate_budget": {
            "max_provider_calls": validated["aggregate_budget"]["max_provider_calls"],
            "max_pixel_edits": validated["aggregate_budget"]["max_pixel_edits"],
            "max_wall_time_ms": validated["aggregate_budget"]["max_wall_time_ms"],
        },
        "aggregate_provider_calls": sum(member["provider_calls"] for member in complete),
        "aggregate_input_tokens": aggregate_input_tokens,
        "aggregate_output_tokens": aggregate_output_tokens,
        "token_accounting_complete": token_accounting_complete,
        "aggregate_pixel_edits": sum(member["pixel_edits"] for member in complete),
        "aggregate_retry_count": sum(member["retry_count"] for member in complete),
        "aggregate_repair_count": sum(member["repair_count"] for member in complete),
        "batch_wall_time_ns": batch_wall_time_ns,
        "scheduler_wall_time_ns": scheduler_wall_time_ns,
        "scheduler_provider_calls": 0,
        "scheduler_input_tokens": 0,
        "scheduler_output_tokens": 0,
        "budget_exhausted": budget.exhausted_dimensions(),
        "failed_member_ids": failed_member_ids,
        "members": complete,
    }

    from .asset_set_execution_validation import validate_asset_set_execution_report

    return validate_asset_set_execution_report(report, validated)
