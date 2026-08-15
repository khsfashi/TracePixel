from __future__ import annotations

import copy
import unittest

from evidence.p3_s7.fixture import art_intent as fixture_art_intent, stage_plan
from tracepixel.agent import (
    AGENT_LOOP_BUDGET_SCHEMA_V1,
    AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
    AgentLoopContractError,
    AgentPreviewFrame,
    run_bounded_edit_loop,
    validate_agent_loop_budget,
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


class _NativePreview:
    def __init__(self) -> None:
        self.calls = 0

    def observe(self, canvas: Canvas) -> AgentPreviewFrame:
        self.calls += 1
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


class AgentLoopTests(unittest.TestCase):
    def test_budget_contract_is_closed_and_rejects_bool(self) -> None:
        valid = _budget()
        self.assertIs(validate_agent_loop_budget(valid), valid)

        for mutation in (
            lambda value: value.update(extra=1),
            lambda value: value.__setitem__("max_iterations", True),
            lambda value: value.__setitem__("max_pixel_edits", -1),
        ):
            candidate = copy.deepcopy(valid)
            mutation(candidate)
            with self.assertRaises(AgentLoopContractError):
                validate_agent_loop_budget(candidate)

    def test_clean_initial_state_finishes_without_provider_or_preview(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(0, 0, (1, 2, 3, 255))
        provider = _FakeProvider()
        preview = _NativePreview()

        result = run_bounded_edit_loop(
            provider,
            canvas=canvas,
            art_intent=_intent(),
            instruction="Ensure the asset is non-empty.",
            qa_evaluator=_NonEmptyQa(),
            preview_observer=preview,
            budget=_budget(),
        )

        self.assertEqual(result.status, "finished")
        self.assertIs(result.canvas, canvas)
        self.assertEqual(result.observation["current"]["revision"], 0)
        self.assertEqual(result.observation["recent"], [])
        self.assertEqual(provider.requests, [])
        self.assertEqual(preview.calls, 0)

    def test_one_valid_edit_runs_qa_and_finishes(self) -> None:
        canvas = Canvas(2, 2)
        provider = _FakeProvider(
            _proposal(_pixel_program([[0, 0, 10, 20, 30, 255]]))
        )
        preview = _NativePreview()

        result = run_bounded_edit_loop(
            provider,
            canvas=canvas,
            art_intent=_intent(),
            instruction="Add one opaque pixel.",
            qa_evaluator=_NonEmptyQa(),
            preview_observer=preview,
            budget=_budget(),
        )

        self.assertEqual(result.status, "finished")
        self.assertEqual(canvas.get_pixel(0, 0), (10, 20, 30, 255))
        self.assertEqual(len(provider.requests), 1)
        request = provider.requests[0]
        self.assertEqual(request["observation"]["current"]["revision"], 0)
        self.assertEqual(len(request["observation"]["qa"]["findings"]), 1)
        self.assertIsNotNone(request["observation"]["preview"])
        self.assertEqual(preview.calls, 1)
        self.assertEqual(result.observation["current"]["revision"], 1)
        self.assertEqual(
            result.observation["recent"],
            [
                {
                    "revision": 0,
                    "stage": None,
                    "proposal_kind": "pixel_program",
                    "operation_count": 1,
                    "changed_pixels": 1,
                }
            ],
        )
        self.assertIsNone(result.observation["preview"])

    def test_noop_revision_is_compact_and_second_revision_can_finish(self) -> None:
        canvas = Canvas(2, 2)
        provider = _FakeProvider(
            _proposal(_pixel_program([[0, 0, 0, 0, 0, 0]])),
            _proposal(_pixel_program([[1, 1, 4, 5, 6, 255]])),
        )

        result = run_bounded_edit_loop(
            provider,
            canvas=canvas,
            art_intent=_intent(),
            instruction="Repair the non-empty finding.",
            qa_evaluator=_NonEmptyQa(),
            budget=_budget(),
        )

        self.assertEqual(result.status, "finished")
        self.assertEqual(len(provider.requests), 2)
        second = provider.requests[1]["observation"]
        self.assertEqual(second["current"]["revision"], 1)
        self.assertEqual(second["recent"][0]["revision"], 0)
        self.assertEqual(second["recent"][0]["changed_pixels"], 0)
        self.assertEqual(result.observation["current"]["revision"], 2)

    def test_iteration_and_tool_budgets_stop_without_extra_provider_call(self) -> None:
        noop = _proposal(_pixel_program([[0, 0, 0, 0, 0, 0]]))
        cases = (
            (_budget(iterations=1, tools=2), "iteration_budget_exhausted"),
            (_budget(iterations=2, tools=1), "tool_budget_exhausted"),
        )
        for budget, expected in cases:
            with self.subTest(expected=expected):
                canvas = Canvas(2, 2)
                provider = _FakeProvider(noop, noop)
                result = run_bounded_edit_loop(
                    provider,
                    canvas=canvas,
                    art_intent=_intent(),
                    instruction="Repair the finding.",
                    qa_evaluator=_NonEmptyQa(),
                    budget=budget,
                )
                self.assertEqual(result.status, expected)
                self.assertEqual(len(provider.requests), 1)
                self.assertEqual(result.observation["current"]["revision"], 1)

    def test_operation_budget_preflight_never_partially_mutates(self) -> None:
        canvas = Canvas(2, 2)
        before = canvas.rgba_bytes()
        provider = _FakeProvider(
            _proposal(
                _pixel_program(
                    [[0, 0, 1, 1, 1, 255]],
                    [[1, 1, 2, 2, 2, 255]],
                )
            )
        )

        result = run_bounded_edit_loop(
            provider,
            canvas=canvas,
            art_intent=_intent(),
            instruction="Repair the finding.",
            qa_evaluator=_NonEmptyQa(),
            budget=_budget(operations=1),
        )

        self.assertEqual(result.status, "operation_budget_exhausted")
        self.assertEqual(canvas.rgba_bytes(), before)
        self.assertEqual(result.observation["current"]["revision"], 0)

    def test_pixel_edit_budget_preflight_never_partially_mutates(self) -> None:
        canvas = Canvas(2, 2)
        before = canvas.rgba_bytes()
        provider = _FakeProvider(
            _proposal(
                _pixel_program(
                    [[0, 0, 1, 1, 1, 255], [1, 1, 2, 2, 2, 255]]
                )
            )
        )

        result = run_bounded_edit_loop(
            provider,
            canvas=canvas,
            art_intent=_intent(),
            instruction="Repair the finding.",
            qa_evaluator=_NonEmptyQa(),
            budget=_budget(edits=1),
        )

        self.assertEqual(result.status, "pixel_edit_budget_exhausted")
        self.assertEqual(canvas.rgba_bytes(), before)
        self.assertEqual(result.observation["current"]["revision"], 0)

    def test_invalid_provider_output_is_rejected_before_mutation(self) -> None:
        canvas = Canvas(2, 2)
        before = canvas.rgba_bytes()
        invalid = {
            "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
            "kind": "pixel_program",
            "payload": _pixel_program([[9, 9, 1, 2, 3, 255]]),
        }
        provider = _FakeProvider(invalid)

        with self.assertRaises(AgentLoopContractError) as raised:
            run_bounded_edit_loop(
                provider,
                canvas=canvas,
                art_intent=_intent(),
                instruction="Repair the finding.",
                qa_evaluator=_NonEmptyQa(),
                budget=_budget(),
            )
        self.assertEqual(raised.exception.code, "invalid_provider_proposal")
        self.assertEqual(canvas.rgba_bytes(), before)

    def test_stage_plan_is_valid_provider_data_but_not_an_a2_edit(self) -> None:
        canvas = Canvas(16, 16)
        provider = _FakeProvider(
            {
                "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
                "kind": "stage_plan",
                "payload": stage_plan(),
            }
        )

        with self.assertRaises(AgentLoopContractError) as raised:
            run_bounded_edit_loop(
                provider,
                canvas=canvas,
                art_intent=fixture_art_intent(),
                instruction="Repair the finding.",
                qa_evaluator=_NonEmptyQa(),
                budget=_budget(),
            )
        self.assertEqual(raised.exception.code, "unsupported_edit_proposal")
        self.assertEqual(canvas.rgba_bytes(), bytes(16 * 16 * 4))

    def test_proposal_canvas_mismatch_is_rejected_before_mutation(self) -> None:
        canvas = Canvas(2, 2)
        provider = _FakeProvider(
            _proposal(
                _pixel_program([[0, 0, 1, 2, 3, 255]], width=3, height=3)
            )
        )

        with self.assertRaises(AgentLoopContractError) as raised:
            run_bounded_edit_loop(
                provider,
                canvas=canvas,
                art_intent=_intent(),
                instruction="Repair the finding.",
                qa_evaluator=_NonEmptyQa(),
                budget=_budget(),
            )
        self.assertEqual(raised.exception.code, "proposal_canvas_mismatch")
        self.assertEqual(canvas.rgba_bytes(), bytes(16))


if __name__ == "__main__":
    unittest.main()
