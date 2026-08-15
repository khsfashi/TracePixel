from __future__ import annotations

import copy
import unittest

from tracepixel.agent import (
    AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1,
    AGENT_LOOP_BUDGET_SCHEMA_V1,
    AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
    AgentMeasuredLoopError,
    AgentPreviewFrame,
    AgentProviderUsage,
    AgentTelemetryContractError,
    run_bounded_edit_loop_with_telemetry,
    validate_agent_complexity_telemetry,
)
from tracepixel.model import ART_INTENT_SCHEMA_V1, PIXEL_PROGRAM_SCHEMA_V1
from tracepixel.qa import QA_POLICY_SCHEMA_V1, analyze_structural, evaluate_qa_policy
from tracepixel.raster import Canvas, export_native_png


class _NonEmptyQa:
    _policy = {
        "schema": QA_POLICY_SCHEMA_V1,
        "rules": [{"rule": "structural.non_empty", "severity": "error"}],
    }

    def evaluate(self, canvas: Canvas):
        return evaluate_qa_policy(
            self._policy,
            structural=analyze_structural(canvas),
        )


class _FakeProvider:
    def __init__(self, *proposals: object) -> None:
        self._proposals = list(proposals)
        self.requests: list[object] = []

    def propose(self, request):
        self.requests.append(copy.deepcopy(request))
        if not self._proposals:
            raise AssertionError("unexpected provider call")
        return self._proposals.pop(0)


class _UsageProvider(_FakeProvider):
    def __init__(
        self,
        proposals: list[object],
        usages: list[AgentProviderUsage | None],
    ) -> None:
        super().__init__(*proposals)
        self._usages = list(usages)
        self._last_usage: AgentProviderUsage | None = None

    def propose(self, request):
        proposal = super().propose(request)
        if not self._usages:
            raise AssertionError("missing usage sample")
        self._last_usage = self._usages.pop(0)
        return proposal

    def last_usage(self) -> AgentProviderUsage | None:
        return self._last_usage


class _NativePreview:
    def observe(self, canvas: Canvas) -> AgentPreviewFrame:
        exported = export_native_png(canvas)
        return AgentPreviewFrame(
            png=exported.png,
            width=exported.metadata.width,
            height=exported.metadata.height,
        )


def _intent(width: int = 2, height: int = 2):
    return {
        "schema": ART_INTENT_SCHEMA_V1,
        "asset_class": "test-icon",
        "canvas": {"width": width, "height": height},
        "composition": {
            "occupied_bounds": None,
            "facing": None,
            "symmetry": None,
            "light_direction": None,
            "palette_budget": None,
        },
    }


def _budget(
    *,
    iterations: int = 4,
    tools: int = 4,
    operations: int = 4,
    edits: int = 16,
):
    return {
        "schema": AGENT_LOOP_BUDGET_SCHEMA_V1,
        "max_iterations": iterations,
        "max_tool_calls": tools,
        "max_operations": operations,
        "max_pixel_edits": edits,
    }


def _pixel_program(*operations: list[list[int]], width: int = 2, height: int = 2):
    return {
        "schema": PIXEL_PROGRAM_SCHEMA_V1,
        "canvas": {"width": width, "height": height},
        "operations": [
            {"op": "set_pixels", "pixels": pixels}
            for pixels in operations
        ],
    }


def _proposal(program: object):
    return {
        "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
        "kind": "pixel_program",
        "payload": program,
    }


class AgentTelemetryTests(unittest.TestCase):
    def test_clean_initial_state_records_zero_work(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(0, 0, (1, 2, 3, 255))

        result = run_bounded_edit_loop_with_telemetry(
            _FakeProvider(),
            canvas=canvas,
            art_intent=_intent(),
            instruction="Ensure the asset is non-empty.",
            qa_evaluator=_NonEmptyQa(),
            budget=_budget(),
        )

        self.assertEqual(result.loop.status, "finished")
        telemetry = result.telemetry
        self.assertEqual(telemetry["schema"], AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1)
        self.assertEqual(telemetry["input_tokens"], 0)
        self.assertEqual(telemetry["output_tokens"], 0)
        self.assertEqual(telemetry["api_cost_usd_micros"], 0)
        self.assertEqual(telemetry["tool_calls"], 0)
        self.assertEqual(telemetry["operation_calls"], 0)
        self.assertEqual(telemetry["exposed_concept_count"], 0)
        self.assertEqual(telemetry["visual_observation_calls"], 0)
        self.assertEqual(telemetry["iterations"], 0)
        self.assertEqual(telemetry["revisions"], 0)
        self.assertEqual(telemetry["changed_pixels"], 0)
        self.assertGreaterEqual(telemetry["wall_time_ns"], 0)
        self.assertEqual(telemetry["human_interventions"], 0)
        self.assertIsNone(telemetry["failure_category"])

    def test_provider_usage_preview_and_accepted_edit_are_counted(self) -> None:
        canvas = Canvas(2, 2)
        provider = _UsageProvider(
            [_proposal(_pixel_program([[0, 0, 10, 20, 30, 255]]))],
            [AgentProviderUsage(input_tokens=120, output_tokens=35, api_cost_usd_micros=420)],
        )

        result = run_bounded_edit_loop_with_telemetry(
            provider,
            canvas=canvas,
            art_intent=_intent(),
            instruction="Add one opaque pixel.",
            qa_evaluator=_NonEmptyQa(),
            preview_observer=_NativePreview(),
            budget=_budget(),
            human_interventions=1,
        )

        telemetry = result.telemetry
        self.assertEqual(result.loop.status, "finished")
        self.assertEqual(telemetry["input_tokens"], 120)
        self.assertEqual(telemetry["output_tokens"], 35)
        self.assertEqual(telemetry["api_cost_usd_micros"], 420)
        self.assertEqual(telemetry["tool_calls"], 1)
        self.assertEqual(telemetry["iterations"], 1)
        self.assertEqual(telemetry["operation_calls"], 1)
        self.assertEqual(telemetry["revisions"], 1)
        self.assertEqual(telemetry["changed_pixels"], 1)
        self.assertGreater(telemetry["exposed_concept_count"], 0)
        self.assertEqual(telemetry["visual_observation_calls"], 1)
        self.assertEqual(telemetry["human_interventions"], 1)
        self.assertIsNone(telemetry["failure_category"])

    def test_usage_aggregate_becomes_unknown_if_any_call_omits_metric(self) -> None:
        canvas = Canvas(2, 2)
        provider = _UsageProvider(
            [
                _proposal(_pixel_program([[0, 0, 0, 0, 0, 0]])),
                _proposal(_pixel_program([[1, 1, 4, 5, 6, 255]])),
            ],
            [
                AgentProviderUsage(input_tokens=10, output_tokens=5, api_cost_usd_micros=7),
                AgentProviderUsage(input_tokens=None, output_tokens=3, api_cost_usd_micros=None),
            ],
        )

        result = run_bounded_edit_loop_with_telemetry(
            provider,
            canvas=canvas,
            art_intent=_intent(),
            instruction="Repair the finding.",
            qa_evaluator=_NonEmptyQa(),
            budget=_budget(),
        )

        telemetry = result.telemetry
        self.assertEqual(telemetry["input_tokens"], None)
        self.assertEqual(telemetry["output_tokens"], 8)
        self.assertEqual(telemetry["api_cost_usd_micros"], None)
        self.assertEqual(telemetry["tool_calls"], 2)
        self.assertEqual(telemetry["operation_calls"], 2)
        self.assertEqual(telemetry["revisions"], 2)
        self.assertEqual(telemetry["changed_pixels"], 1)

    def test_over_budget_candidate_is_not_counted_as_accepted_operation_or_revision(self) -> None:
        canvas = Canvas(2, 2)
        provider = _FakeProvider(
            _proposal(
                _pixel_program(
                    [[0, 0, 1, 1, 1, 255]],
                    [[1, 1, 2, 2, 2, 255]],
                )
            )
        )

        result = run_bounded_edit_loop_with_telemetry(
            provider,
            canvas=canvas,
            art_intent=_intent(),
            instruction="Repair the finding.",
            qa_evaluator=_NonEmptyQa(),
            budget=_budget(operations=1),
        )

        telemetry = result.telemetry
        self.assertEqual(result.loop.status, "operation_budget_exhausted")
        self.assertEqual(telemetry["tool_calls"], 1)
        self.assertEqual(telemetry["iterations"], 1)
        self.assertEqual(telemetry["operation_calls"], 0)
        self.assertEqual(telemetry["revisions"], 0)
        self.assertEqual(telemetry["changed_pixels"], 0)
        self.assertEqual(telemetry["failure_category"], "budget.operation")
        self.assertIsNone(telemetry["input_tokens"])

    def test_contract_failure_carries_telemetry_without_mutation(self) -> None:
        canvas = Canvas(2, 2)
        before = canvas.rgba_bytes()
        invalid = {
            "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
            "kind": "pixel_program",
            "payload": _pixel_program([[9, 9, 1, 2, 3, 255]]),
        }

        with self.assertRaises(AgentMeasuredLoopError) as raised:
            run_bounded_edit_loop_with_telemetry(
                _FakeProvider(invalid),
                canvas=canvas,
                art_intent=_intent(),
                instruction="Repair the finding.",
                qa_evaluator=_NonEmptyQa(),
                budget=_budget(),
            )

        self.assertEqual(raised.exception.cause.code, "invalid_provider_proposal")
        telemetry = raised.exception.telemetry
        self.assertEqual(telemetry["failure_category"], "contract.invalid_provider_proposal")
        self.assertEqual(telemetry["tool_calls"], 1)
        self.assertEqual(telemetry["revisions"], 0)
        self.assertEqual(telemetry["changed_pixels"], 0)
        self.assertEqual(canvas.rgba_bytes(), before)

    def test_telemetry_contract_is_closed_and_rejects_bool(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(0, 0, (1, 2, 3, 255))
        valid = run_bounded_edit_loop_with_telemetry(
            _FakeProvider(),
            canvas=canvas,
            art_intent=_intent(),
            instruction="Ensure the asset is non-empty.",
            qa_evaluator=_NonEmptyQa(),
            budget=_budget(),
        ).telemetry
        self.assertIs(validate_agent_complexity_telemetry(valid), valid)

        extra = dict(valid)
        extra["extra"] = 1
        with self.assertRaises(AgentTelemetryContractError):
            validate_agent_complexity_telemetry(extra)

        invalid_bool = dict(valid)
        invalid_bool["tool_calls"] = True
        with self.assertRaises(AgentTelemetryContractError):
            validate_agent_complexity_telemetry(invalid_bool)

        invalid_failure = dict(valid)
        invalid_failure["failure_category"] = "Bad Category"
        with self.assertRaises(AgentTelemetryContractError):
            validate_agent_complexity_telemetry(invalid_failure)

    def test_human_interventions_rejects_bool_and_negative_values(self) -> None:
        for value in (True, -1):
            with self.subTest(value=value):
                with self.assertRaises(AgentTelemetryContractError):
                    run_bounded_edit_loop_with_telemetry(
                        _FakeProvider(),
                        canvas=Canvas(2, 2),
                        art_intent=_intent(),
                        instruction="Repair the finding.",
                        qa_evaluator=_NonEmptyQa(),
                        budget=_budget(),
                        human_interventions=value,
                    )


if __name__ == "__main__":
    unittest.main()
