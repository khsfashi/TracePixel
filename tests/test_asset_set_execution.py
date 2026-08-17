from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from threading import Barrier, Lock
import unittest

from tracepixel.model.asset_set_execution_validation import (
    AssetSetExecutionValidationError,
    validate_asset_set_execution_report,
)
from tracepixel.model.asset_set_executor import (
    AssetSetMemberExecutionContext,
    SingleAssetExecutionOutput,
    execute_asset_set_schedule,
)
from tracepixel.model.asset_set_schedule import ASSET_REQUEST_SCHEMA_V1, ASSET_SET_REQUEST_SCHEMA_V1
from tracepixel.model.asset_set_schedule_validation import (
    asset_request_sha256,
    asset_set_sha256,
    build_asset_set_schedule,
)

_STYLE = {
    "kind": "style",
    "profile_id": "small-rpg-icons",
    "profile_schema": "tracepixel.style-profile.v1",
    "sha256": "1" * 64,
}


def _asset_set(
    *,
    max_concurrency: int = 2,
    max_provider_calls: int = 8,
    max_pixel_edits: int = 128,
    max_wall_time_ms: int = 60_000,
) -> dict[str, object]:
    return {
        "schema": "tracepixel.asset-set.v1",
        "asset_set_id": "starter-icons",
        "shared_profiles": [deepcopy(_STYLE)],
        "members": [
            {"member_id": "potion-red", "request_ref": "requests/potion-red.json"},
            {"member_id": "potion-blue", "request_ref": "requests/potion-blue.json"},
            {"member_id": "leaf-green", "request_ref": "requests/leaf-green.json"},
        ],
        "execution": {
            "member_authority": "single-asset-pipeline",
            "ordering": "declared-member-order",
            "failure_policy": "isolate-member",
            "max_concurrency": max_concurrency,
            "aggregate_budget": {
                "max_provider_calls": max_provider_calls,
                "max_pixel_edits": max_pixel_edits,
                "max_wall_time_ms": max_wall_time_ms,
            },
        },
    }


def _art_intent() -> dict[str, object]:
    return {
        "schema": "tracepixel.art-intent.v1",
        "asset_class": "item-icon",
        "canvas": {"width": 16, "height": 16},
        "composition": {
            "occupied_bounds": {"x": 3, "y": 2, "width": 10, "height": 12},
            "facing": "front",
            "symmetry": {"axis": "vertical", "strength": "hint"},
            "light_direction": "top_left",
            "palette_budget": 8,
        },
    }


def _asset_request(instruction: str) -> dict[str, object]:
    return {
        "schema": ASSET_REQUEST_SCHEMA_V1,
        "instruction": instruction,
        "art_intent": _art_intent(),
        "profile_refs": [deepcopy(_STYLE)],
    }


def _payloads() -> dict[str, object]:
    return {
        "requests/potion-red.json": _asset_request("Create a red healing potion icon."),
        "requests/potion-blue.json": _asset_request("Create a blue mana potion icon."),
        "requests/leaf-green.json": _asset_request("Create a green leaf item icon."),
    }


def _bound_inputs(asset_set: dict[str, object]) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    payloads = _payloads()
    members = asset_set["members"]
    shared = asset_set["shared_profiles"]
    assert type(members) is list and type(shared) is list
    request_set = {
        "schema": ASSET_SET_REQUEST_SCHEMA_V1,
        "asset_set_id": asset_set["asset_set_id"],
        "asset_set_sha256": asset_set_sha256(asset_set),
        "members": [
            {
                "member_id": member["member_id"],
                "request_ref": member["request_ref"],
                "request_sha256": asset_request_sha256(
                    payloads[member["request_ref"]],
                    shared_profiles=shared,
                ),
            }
            for member in members
        ],
    }
    return payloads, request_set, build_asset_set_schedule(request_set, asset_set, payloads)


def _digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class _RecordedExecutor:
    def __init__(
        self,
        *,
        fail_member: str | None = None,
        reuse_member: str | None = None,
        barrier: Barrier | None = None,
        leave_usage_open_for: str | None = None,
        provider_calls_per_member: int = 1,
        pixel_edits_per_member: int = 4,
    ) -> None:
        self.fail_member = fail_member
        self.reuse_member = reuse_member
        self.barrier = barrier
        self.leave_usage_open_for = leave_usage_open_for
        self.provider_calls_per_member = provider_calls_per_member
        self.pixel_edits_per_member = pixel_edits_per_member
        self.calls: dict[str, int] = {}
        self._lock = Lock()

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

        if self.barrier is not None and member_id in ("potion-red", "potion-blue"):
            self.barrier.wait(timeout=5)

        if self.reuse_member == member_id:
            digest = _digest(f"cached:{member_id}")
            return SingleAssetExecutionOutput(
                status="succeeded",
                result_ref=f"results/{member_id}.json",
                result_sha256=digest,
                cache_decision="reused",
                source_request_sha256=request_sha256,
                source_result_ref=f"cache/{member_id}.json",
                source_result_sha256=digest,
                deterministic_qa_ref=f"qa/{member_id}.json",
                complexity_ref=f"complexity/{member_id}.json",
                provenance_ref=f"provenance/{member_id}.json",
            )

        for call_index in range(self.provider_calls_per_member):
            context.before_provider_call()
            if self.leave_usage_open_for == member_id and call_index == 0:
                raise RuntimeError("provider usage unavailable")
            context.after_provider_call(
                input_tokens=10 + call_index,
                output_tokens=4 + call_index,
            )
        context.before_pixel_edits(self.pixel_edits_per_member)

        if self.fail_member == member_id:
            context.record_retry("recorded-provider-retry")
            context.record_repair("deterministic-local-repair")
            return SingleAssetExecutionOutput(
                status="failed",
                failure_category="recorded.member_failure",
                failure_reason="synthetic provider-free failure",
            )

        digest = _digest(f"result:{member_id}")
        return SingleAssetExecutionOutput(
            status="succeeded",
            result_ref=f"results/{member_id}.json",
            result_sha256=digest,
            deterministic_qa_ref=f"qa/{member_id}.json",
            complexity_ref=f"complexity/{member_id}.json",
            provenance_ref=f"provenance/{member_id}.json",
        )


class AssetSetExecutionTests(unittest.TestCase):
    def test_declared_order_execution_is_bounded_and_exactly_reconciled(self) -> None:
        asset_set = _asset_set(max_concurrency=2)
        payloads, request_set, schedule = _bound_inputs(asset_set)
        executor = _RecordedExecutor(barrier=Barrier(2))

        report = execute_asset_set_schedule(schedule, request_set, asset_set, payloads, executor)

        self.assertEqual(2, report["observed_peak_live_members"])
        self.assertLessEqual(report["observed_peak_live_members"], report["declared_max_concurrency"])
        self.assertEqual(
            ["potion-red", "potion-blue", "leaf-green"],
            [member["member_id"] for member in report["members"]],
        )
        self.assertEqual(3, report["aggregate_provider_calls"])
        self.assertEqual(30, report["aggregate_input_tokens"])
        self.assertEqual(12, report["aggregate_output_tokens"])
        self.assertEqual(12, report["aggregate_pixel_edits"])
        self.assertEqual(0, report["scheduler_provider_calls"])
        self.assertEqual(0, report["scheduler_input_tokens"])
        self.assertEqual(0, report["scheduler_output_tokens"])
        self.assertTrue(report["token_accounting_complete"])
        self.assertEqual({}, {member: count for member, count in executor.calls.items() if count != 1})

    def test_member_failure_is_isolated_and_successful_siblings_are_not_restarted(self) -> None:
        asset_set = _asset_set()
        payloads, request_set, schedule = _bound_inputs(asset_set)
        executor = _RecordedExecutor(fail_member="potion-blue")

        report = execute_asset_set_schedule(schedule, request_set, asset_set, payloads, executor)

        self.assertEqual(["potion-blue"], report["failed_member_ids"])
        self.assertEqual(
            ["succeeded", "failed", "succeeded"],
            [member["status"] for member in report["members"]],
        )
        self.assertEqual({"potion-red": 1, "potion-blue": 1, "leaf-green": 1}, executor.calls)
        failed = report["members"][1]
        self.assertEqual(1, failed["retry_count"])
        self.assertEqual(["recorded-provider-retry"], failed["retry_reasons"])
        self.assertEqual(1, failed["repair_count"])
        self.assertEqual(["deterministic-local-repair"], failed["repair_reasons"])

    def test_provider_budget_is_reserved_before_calls_and_exhaustion_is_retained(self) -> None:
        asset_set = _asset_set(max_concurrency=1, max_provider_calls=2)
        payloads, request_set, schedule = _bound_inputs(asset_set)
        executor = _RecordedExecutor()

        report = execute_asset_set_schedule(schedule, request_set, asset_set, payloads, executor)

        self.assertEqual(2, report["aggregate_provider_calls"])
        self.assertIn("provider_calls", report["budget_exhausted"])
        self.assertEqual("budget_exhausted", report["members"][2]["status"])
        self.assertEqual("budget.provider_calls", report["members"][2]["failure_category"])
        self.assertLessEqual(
            report["aggregate_provider_calls"],
            report["aggregate_budget"]["max_provider_calls"],
        )

    def test_pixel_edit_budget_is_reserved_before_raster_work(self) -> None:
        asset_set = _asset_set(max_concurrency=1, max_pixel_edits=5)
        payloads, request_set, schedule = _bound_inputs(asset_set)
        executor = _RecordedExecutor(pixel_edits_per_member=4)

        report = execute_asset_set_schedule(schedule, request_set, asset_set, payloads, executor)

        self.assertEqual(4, report["aggregate_pixel_edits"])
        self.assertIn("pixel_edits", report["budget_exhausted"])
        self.assertEqual("budget_exhausted", report["members"][1]["status"])
        self.assertLessEqual(
            report["aggregate_pixel_edits"],
            report["aggregate_budget"]["max_pixel_edits"],
        )

    def test_cache_reuse_is_explicit_and_has_zero_new_member_cost(self) -> None:
        asset_set = _asset_set()
        payloads, request_set, schedule = _bound_inputs(asset_set)
        executor = _RecordedExecutor(reuse_member="leaf-green")

        report = execute_asset_set_schedule(schedule, request_set, asset_set, payloads, executor)
        reused = report["members"][2]

        self.assertEqual("reused", reused["cache"]["decision"])
        self.assertEqual(reused["request_sha256"], reused["cache"]["source_request_sha256"])
        self.assertEqual(0, reused["provider_calls"])
        self.assertEqual(0, reused["input_tokens"])
        self.assertEqual(0, reused["output_tokens"])
        self.assertEqual(0, reused["pixel_edits"])

    def test_unreported_provider_usage_fails_member_closed_without_losing_siblings(self) -> None:
        asset_set = _asset_set(max_concurrency=1)
        payloads, request_set, schedule = _bound_inputs(asset_set)
        executor = _RecordedExecutor(leave_usage_open_for="potion-blue")

        report = execute_asset_set_schedule(schedule, request_set, asset_set, payloads, executor)

        failed = report["members"][1]
        self.assertEqual("failed", failed["status"])
        self.assertFalse(failed["token_accounting_complete"])
        self.assertIsNone(failed["input_tokens"])
        self.assertIsNone(failed["output_tokens"])
        self.assertFalse(report["token_accounting_complete"])
        self.assertIsNone(report["aggregate_input_tokens"])
        self.assertIsNone(report["aggregate_output_tokens"])
        self.assertEqual("succeeded", report["members"][0]["status"])
        self.assertEqual("succeeded", report["members"][2]["status"])

    def test_validator_rejects_hidden_scheduler_cost_or_tampered_aggregate(self) -> None:
        asset_set = _asset_set()
        payloads, request_set, schedule = _bound_inputs(asset_set)
        report = execute_asset_set_schedule(
            schedule,
            request_set,
            asset_set,
            payloads,
            _RecordedExecutor(),
        )

        tampered = deepcopy(report)
        tampered["scheduler_provider_calls"] = 1
        with self.assertRaisesRegex(AssetSetExecutionValidationError, "scheduler_provider_work"):
            validate_asset_set_execution_report(tampered, schedule)

        tampered = deepcopy(report)
        tampered["aggregate_provider_calls"] += 1
        with self.assertRaisesRegex(AssetSetExecutionValidationError, "aggregate_mismatch"):
            validate_asset_set_execution_report(tampered, schedule)

        tampered = deepcopy(report)
        tampered["observed_peak_live_members"] = schedule["max_concurrency"] + 1
        with self.assertRaisesRegex(AssetSetExecutionValidationError, "concurrency_exceeded"):
            validate_asset_set_execution_report(tampered, schedule)


if __name__ == "__main__":
    unittest.main()
