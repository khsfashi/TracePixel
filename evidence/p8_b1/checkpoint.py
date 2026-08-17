from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from threading import Barrier, Lock
from typing import cast

from tracepixel.model.asset_set_executor import (
    AssetSetMemberExecutionContext,
    SingleAssetExecutionOutput,
    execute_asset_set_schedule,
)
from tracepixel.model.asset_set_schedule_validation import validate_asset_set_schedule
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


class _RecordedSingleAssetExecutor:
    """Provider-free deterministic executor that exercises only the B1 accounting seam."""

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


def _validate_lane(lane: dict[str, object]) -> None:
    if lane.get("current") != "P8" or lane.get("active_issue") != 92:
        raise SystemExit("P8-B1 checkpoint requires live P8 / issue #92")
    children = lane.get("child_sequences")
    if type(children) is not dict:
        raise SystemExit("core lane child_sequences malformed")
    p8 = cast(dict[str, object], children).get("P8")
    child = lane.get("current_child")
    if type(p8) is not list or child not in cast(list[object], p8):
        raise SystemExit("active P8 child is not declared")
    names = cast(list[str], p8)
    if names.index(cast(str, child)) < names.index("P8-C0"):
        raise SystemExit("P8-B1 completion must hand off to P8-C0 before this checkpoint is green")


def main() -> int:
    asset_set = validate_asset_set(_json(ASSET_SET))
    request_set = _json(REQUEST_SET)
    schedule = _json(SCHEDULE)

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

    validated_schedule = validate_asset_set_schedule(
        schedule,
        request_set,
        asset_set,
        payloads,
    )
    if validated_schedule["max_concurrency"] <= 1:
        raise SystemExit("P8-B1 checkpoint requires a representative bounded concurrent schedule")

    executor = _RecordedSingleAssetExecutor()
    report = execute_asset_set_schedule(
        validated_schedule,
        request_set,
        asset_set,
        payloads,
        executor,
    )

    if report["observed_peak_live_members"] != 2:
        raise SystemExit("checkpoint did not exercise two simultaneously live members")
    if report["observed_peak_live_members"] > report["declared_max_concurrency"]:
        raise SystemExit("observed concurrency exceeded declared max_concurrency")
    if report["scheduler_provider_calls"] != 0:
        raise SystemExit("scheduler provider calls must be zero")
    if report["scheduler_input_tokens"] != 0 or report["scheduler_output_tokens"] != 0:
        raise SystemExit("scheduler tokens must be zero")
    if report["aggregate_provider_calls"] != 2:
        raise SystemExit("unexpected provider-call total")
    if report["aggregate_input_tokens"] != 22 or report["aggregate_output_tokens"] != 10:
        raise SystemExit("member token totals did not reconcile exactly")
    if report["aggregate_pixel_edits"] != 8:
        raise SystemExit("unexpected pixel-edit total")
    if report["failed_member_ids"] != ["potion-blue"]:
        raise SystemExit("member-local failure was not retained exactly")
    if report["aggregate_retry_count"] != 1 or report["aggregate_repair_count"] != 1:
        raise SystemExit("member-local retry/repair telemetry was not retained")
    if executor.calls != {"potion-red": 1, "potion-blue": 1, "leaf-green": 1}:
        raise SystemExit("successful siblings were restarted or a member was not executed exactly once")

    red, blue, leaf = report["members"]
    if red["status"] != "succeeded" or blue["status"] != "failed" or leaf["status"] != "succeeded":
        raise SystemExit("member statuses do not prove isolated failure retention")
    if leaf["cache"]["decision"] != "reused":
        raise SystemExit("cache/reuse outcome was not exercised")
    if any((leaf["provider_calls"], leaf["input_tokens"], leaf["output_tokens"], leaf["pixel_edits"])):
        raise SystemExit("reused member must have zero new cost")
    if report["budget_exhausted"]:
        raise SystemExit("reference execution should remain within every aggregate budget")

    _validate_lane(_json(CORE_LANE))
    print(
        json.dumps(
            {
                "schema": "tracepixel.p8-b1-checkpoint.v1",
                "member_count": len(report["members"]),
                "declared_max_concurrency": report["declared_max_concurrency"],
                "observed_peak_live_members": report["observed_peak_live_members"],
                "aggregate_provider_calls": report["aggregate_provider_calls"],
                "aggregate_input_tokens": report["aggregate_input_tokens"],
                "aggregate_output_tokens": report["aggregate_output_tokens"],
                "aggregate_pixel_edits": report["aggregate_pixel_edits"],
                "scheduler_provider_calls": report["scheduler_provider_calls"],
                "scheduler_input_tokens": report["scheduler_input_tokens"],
                "scheduler_output_tokens": report["scheduler_output_tokens"],
                "failure_isolation": True,
                "cache_reuse": True,
                "provider_invoked": False,
                "raster_authority_created": False,
                "next": "P8-C0",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
