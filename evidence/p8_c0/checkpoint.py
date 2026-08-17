from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from threading import Barrier, Lock
from time import sleep
from typing import cast

from tracepixel.model.asset_set_executor import (
    AssetSetMemberExecutionContext,
    SingleAssetExecutionOutput,
    execute_asset_set_schedule,
)
from tracepixel.model.asset_set_schedule_validation import (
    asset_set_sha256,
    build_asset_set_schedule,
    validate_asset_set_schedule,
)
from tracepixel.model.asset_set_validation import validate_asset_set

ROOT = Path(__file__).resolve().parents[2]
ASSET_SET = ROOT / "evidence" / "p8_x0" / "reference-asset-set.v1.json"
REQUEST_SET = ROOT / "evidence" / "p8_b0" / "reference-asset-set-request.v1.json"
SCHEDULE = ROOT / "evidence" / "p8_b0" / "reference-asset-set-schedule.v1.json"
REQUEST_ROOT = ROOT / "evidence" / "p8_b0"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _payloads(request_set: dict[str, object]) -> dict[str, object]:
    raw_members = request_set.get("members")
    if type(raw_members) is not list:
        raise SystemExit("request manifest members malformed")
    payloads: dict[str, object] = {}
    for raw in cast(list[object], raw_members):
        if type(raw) is not dict:
            raise SystemExit("request manifest member malformed")
        ref = cast(dict[str, object], raw).get("request_ref")
        if type(ref) is not str:
            raise SystemExit("request_ref malformed")
        payloads[ref] = _json(REQUEST_ROOT / ref)
    return payloads


def _derived_inputs(
    asset_set: dict[str, object],
    request_set: dict[str, object],
    payloads: dict[str, object],
    *,
    max_concurrency: int | None = None,
    max_provider_calls: int | None = None,
    max_wall_time_ms: int | None = None,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    derived_set = deepcopy(asset_set)
    execution = derived_set.get("execution")
    if type(execution) is not dict:
        raise SystemExit("AssetSet execution contract malformed")
    execution_typed = cast(dict[str, object], execution)
    budget = execution_typed.get("aggregate_budget")
    if type(budget) is not dict:
        raise SystemExit("AssetSet aggregate budget malformed")
    budget_typed = cast(dict[str, object], budget)

    if max_concurrency is not None:
        execution_typed["max_concurrency"] = max_concurrency
    if max_provider_calls is not None:
        budget_typed["max_provider_calls"] = max_provider_calls
    if max_wall_time_ms is not None:
        budget_typed["max_wall_time_ms"] = max_wall_time_ms

    validate_asset_set(derived_set)
    derived_request_set = deepcopy(request_set)
    derived_request_set["asset_set_sha256"] = asset_set_sha256(derived_set)
    schedule = build_asset_set_schedule(derived_request_set, derived_set, payloads)
    return derived_set, derived_request_set, cast(dict[str, object], schedule)


class _PrimaryExecutor:
    """Recorded provider-free execution with one local failure and one immutable cache hit."""

    def __init__(self) -> None:
        self._barrier = Barrier(2)
        self._lock = Lock()
        self.calls: dict[str, int] = {}

    def execute(
        self,
        request: object,
        /,
        *,
        member_id: str,
        request_sha256: str,
        context: AssetSetMemberExecutionContext,
    ) -> SingleAssetExecutionOutput:
        with self._lock:
            self.calls[member_id] = self.calls.get(member_id, 0) + 1

        if member_id in ("potion-red", "potion-blue"):
            self._barrier.wait(timeout=5)

        if member_id == "leaf-green":
            result_sha = _digest("retained-cache:leaf-green")
            return SingleAssetExecutionOutput(
                status="succeeded",
                result_ref="results/leaf-green.json",
                result_sha256=result_sha,
                cache_decision="reused",
                source_request_sha256=request_sha256,
                source_result_ref="cache/leaf-green.json",
                source_result_sha256=result_sha,
                deterministic_qa_ref="qa/leaf-green.json",
                complexity_ref="complexity/leaf-green.json",
                provenance_ref="provenance/leaf-green.json",
            )

        context.before_provider_call()
        context.after_provider_call(input_tokens=11, output_tokens=5)
        context.before_pixel_edits(4)

        if member_id == "potion-blue":
            context.record_retry("recorded-provider-retry")
            context.record_repair("deterministic-local-repair")
            return SingleAssetExecutionOutput(
                status="failed",
                failure_category="recorded.member_failure",
                failure_reason="synthetic provider-free failure",
            )

        return SingleAssetExecutionOutput(
            status="succeeded",
            result_ref="results/potion-red.json",
            result_sha256=_digest("result:potion-red"),
            deterministic_qa_ref="qa/potion-red.json",
            complexity_ref="complexity/potion-red.json",
            provenance_ref="provenance/potion-red.json",
        )


class _TargetedRetryExecutor:
    """Retry the failed member while successful siblings are immutable zero-cost reuse."""

    def __init__(self, retained_successes: dict[str, dict[str, object]]) -> None:
        self._retained_successes = retained_successes

    def execute(
        self,
        request: object,
        /,
        *,
        member_id: str,
        request_sha256: str,
        context: AssetSetMemberExecutionContext,
    ) -> SingleAssetExecutionOutput:
        prior = self._retained_successes.get(member_id)
        if prior is not None:
            result_ref = cast(str, prior["result_ref"])
            result_sha = cast(str, prior["result_sha256"])
            return SingleAssetExecutionOutput(
                status="succeeded",
                result_ref=result_ref,
                result_sha256=result_sha,
                cache_decision="reused",
                source_request_sha256=request_sha256,
                source_result_ref=result_ref,
                source_result_sha256=result_sha,
                deterministic_qa_ref=f"qa/{member_id}.json",
                complexity_ref=f"complexity/{member_id}.json",
                provenance_ref=f"provenance/{member_id}.json",
            )

        if member_id != "potion-blue":
            raise RuntimeError("only the previously failed member may execute new work")

        context.before_provider_call()
        context.after_provider_call(input_tokens=13, output_tokens=6)
        context.before_pixel_edits(4)
        return SingleAssetExecutionOutput(
            status="succeeded",
            result_ref="results/potion-blue-retry.json",
            result_sha256=_digest("result:potion-blue:retry"),
            deterministic_qa_ref="qa/potion-blue-retry.json",
            complexity_ref="complexity/potion-blue-retry.json",
            provenance_ref="provenance/potion-blue-retry.json",
        )


class _ProviderBudgetExecutor:
    def execute(
        self,
        request: object,
        /,
        *,
        member_id: str,
        request_sha256: str,
        context: AssetSetMemberExecutionContext,
    ) -> SingleAssetExecutionOutput:
        context.before_provider_call()
        context.after_provider_call(input_tokens=7, output_tokens=3)
        return SingleAssetExecutionOutput(
            status="succeeded",
            result_ref=f"results/{member_id}-budget.json",
            result_sha256=_digest(f"provider-budget:{member_id}"),
        )


class _WallBudgetExecutor:
    def execute(
        self,
        request: object,
        /,
        *,
        member_id: str,
        request_sha256: str,
        context: AssetSetMemberExecutionContext,
    ) -> SingleAssetExecutionOutput:
        if member_id == "potion-red":
            sleep(0.02)
        return SingleAssetExecutionOutput(
            status="succeeded",
            result_ref=f"results/{member_id}-wall.json",
            result_sha256=_digest(f"wall-budget:{member_id}"),
        )


def _assert_exact_accounting(report: dict[str, object]) -> None:
    members = cast(list[dict[str, object]], report["members"])
    provider_calls = sum(cast(int, member["provider_calls"]) for member in members)
    if report["aggregate_provider_calls"] != provider_calls + report["scheduler_provider_calls"]:
        raise SystemExit("provider-call accounting did not reconcile exactly")

    if report["token_accounting_complete"] is not True:
        raise SystemExit("P8-C0 representative evidence requires complete provider token accounting")
    input_tokens = sum(cast(int, member["input_tokens"]) for member in members)
    output_tokens = sum(cast(int, member["output_tokens"]) for member in members)
    if report["aggregate_input_tokens"] != input_tokens + report["scheduler_input_tokens"]:
        raise SystemExit("input-token accounting did not reconcile exactly")
    if report["aggregate_output_tokens"] != output_tokens + report["scheduler_output_tokens"]:
        raise SystemExit("output-token accounting did not reconcile exactly")

    if any(
        report[field] != 0
        for field in (
            "scheduler_provider_calls",
            "scheduler_input_tokens",
            "scheduler_output_tokens",
        )
    ):
        raise SystemExit("P8-C0 forbids scheduler provider/token work before P8-B2")


def _validate_lane(lane: dict[str, object]) -> None:
    if lane.get("current") != "P8" or lane.get("active_issue") != 92:
        raise SystemExit("P8-C0 checkpoint requires live P8 / issue #92")
    children = lane.get("child_sequences")
    if type(children) is not dict:
        raise SystemExit("core lane child_sequences malformed")
    p8 = cast(dict[str, object], children).get("P8")
    child = lane.get("current_child")
    if type(p8) is not list or child not in cast(list[object], p8):
        raise SystemExit("active P8 child is not declared")
    names = cast(list[str], p8)
    if names.index("P8-C0") + 1 != names.index("P8-B2"):
        raise SystemExit("P8-C0 must remain the immediate gate before P8-B2")
    if names.index(cast(str, child)) < names.index("P8-B2"):
        raise SystemExit("green P8-C0 must hand the core lane to P8-B2")


def main() -> int:
    asset_set = cast(dict[str, object], validate_asset_set(_json(ASSET_SET)))
    request_set = _json(REQUEST_SET)
    payloads = _payloads(request_set)
    schedule = validate_asset_set_schedule(_json(SCHEDULE), request_set, asset_set, payloads)

    if schedule["max_concurrency"] <= 1:
        raise SystemExit("P8-C0 requires a representative bounded concurrent execution")

    primary_executor = _PrimaryExecutor()
    primary = cast(
        dict[str, object],
        execute_asset_set_schedule(schedule, request_set, asset_set, payloads, primary_executor),
    )
    _assert_exact_accounting(primary)

    if primary["observed_peak_live_members"] != 2:
        raise SystemExit("representative execution did not prove bounded concurrency > 1")
    if cast(int, primary["observed_peak_live_members"]) > cast(int, primary["declared_max_concurrency"]):
        raise SystemExit("observed concurrency exceeded declared max_concurrency")
    if primary["failed_member_ids"] != ["potion-blue"]:
        raise SystemExit("representative execution must retain exactly one local failure")
    if primary_executor.calls != {"potion-red": 1, "potion-blue": 1, "leaf-green": 1}:
        raise SystemExit("member failure caused a sibling restart or duplicate execution")

    primary_members = cast(list[dict[str, object]], primary["members"])
    retained_successes = {
        cast(str, member["member_id"]): member
        for member in primary_members
        if member["status"] == "succeeded"
    }
    if set(retained_successes) != {"potion-red", "leaf-green"}:
        raise SystemExit("expected successful siblings were not retained")

    retry = cast(
        dict[str, object],
        execute_asset_set_schedule(
            schedule,
            request_set,
            asset_set,
            payloads,
            _TargetedRetryExecutor(retained_successes),
        ),
    )
    _assert_exact_accounting(retry)
    if retry["failed_member_ids"]:
        raise SystemExit("targeted retry should recover the previously failed member")
    if retry["aggregate_provider_calls"] != 1:
        raise SystemExit("targeted retry must add provider work only for the affected member")
    if retry["aggregate_input_tokens"] != 13 or retry["aggregate_output_tokens"] != 6:
        raise SystemExit("targeted retry token totals must contain only affected-member work")

    retry_members = {
        cast(str, member["member_id"]): member
        for member in cast(list[dict[str, object]], retry["members"])
    }
    for member_id in ("potion-red", "leaf-green"):
        before = retained_successes[member_id]
        after = retry_members[member_id]
        if after["cache"]["decision"] != "reused":
            raise SystemExit("successful sibling was not reused during targeted retry")
        if after["result_ref"] != before["result_ref"] or after["result_sha256"] != before["result_sha256"]:
            raise SystemExit("successful sibling result identity changed during another member retry")
        if any((after["provider_calls"], after["input_tokens"], after["output_tokens"], after["pixel_edits"])):
            raise SystemExit("successful sibling incurred new provider/token/pixel cost during retry")

    provider_set, provider_request_set, provider_schedule = _derived_inputs(
        asset_set,
        request_set,
        payloads,
        max_concurrency=1,
        max_provider_calls=1,
    )
    provider_budget = cast(
        dict[str, object],
        execute_asset_set_schedule(
            provider_schedule,
            provider_request_set,
            provider_set,
            payloads,
            _ProviderBudgetExecutor(),
        ),
    )
    _assert_exact_accounting(provider_budget)
    if provider_budget["aggregate_provider_calls"] != 1:
        raise SystemExit("provider-call budget was not reserved before provider invocation")
    if "provider_calls" not in cast(list[object], provider_budget["budget_exhausted"]):
        raise SystemExit("provider-call budget exhaustion was not retained")
    if any(
        member["status"] != "budget_exhausted"
        for member in cast(list[dict[str, object]], provider_budget["members"])[1:]
    ):
        raise SystemExit("members advancing past the provider-call ceiling were not blocked")

    wall_set, wall_request_set, wall_schedule = _derived_inputs(
        asset_set,
        request_set,
        payloads,
        max_concurrency=1,
        max_wall_time_ms=2,
    )
    wall_budget = cast(
        dict[str, object],
        execute_asset_set_schedule(
            wall_schedule,
            wall_request_set,
            wall_set,
            payloads,
            _WallBudgetExecutor(),
        ),
    )
    _assert_exact_accounting(wall_budget)
    wall_members = cast(list[dict[str, object]], wall_budget["members"])
    if wall_members[0]["status"] != "succeeded":
        raise SystemExit("wall-time evidence requires the admitted first member to remain retained")
    if any(member["status"] != "budget_exhausted" for member in wall_members[1:]):
        raise SystemExit("wall-time exhaustion did not stop later member admission")
    if "wall_time" not in cast(list[object], wall_budget["budget_exhausted"]):
        raise SystemExit("wall-time budget exhaustion was not retained")
    if wall_budget["aggregate_provider_calls"] != 0:
        raise SystemExit("wall-time admission case unexpectedly invoked provider work")

    if cast(int, primary["batch_wall_time_ns"]) <= 0 or cast(int, retry["batch_wall_time_ns"]) <= 0:
        raise SystemExit("descriptive batch wall-time evidence was not retained")

    _validate_lane(_json(CORE_LANE))
    print(
        json.dumps(
            {
                "schema": "tracepixel.p8-c0-cost-scaling-checkpoint.v1",
                "result": "green",
                "member_count": len(primary_members),
                "declared_max_concurrency": primary["declared_max_concurrency"],
                "observed_peak_live_members": primary["observed_peak_live_members"],
                "primary_provider_calls": primary["aggregate_provider_calls"],
                "primary_input_tokens": primary["aggregate_input_tokens"],
                "primary_output_tokens": primary["aggregate_output_tokens"],
                "scheduler_provider_calls": primary["scheduler_provider_calls"],
                "scheduler_input_tokens": primary["scheduler_input_tokens"],
                "scheduler_output_tokens": primary["scheduler_output_tokens"],
                "failure_isolation": True,
                "targeted_retry_provider_calls": retry["aggregate_provider_calls"],
                "successful_sibling_reuse": True,
                "provider_budget_enforced": True,
                "wall_time_admission_enforced": True,
                "descriptive_wall_time_retained": True,
                "deterministic_wall_time_threshold_claim": False,
                "b1_single_asset_cost_solved": False,
                "provider_invoked": False,
                "next": "P8-B2",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
