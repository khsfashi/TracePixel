from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tracepixel.benchmark.b1_adapters import (
    B1_RAW_METHOD_ID,
    B1_STAGE_SEQUENCE_V1,
    B1_TRACEPIXEL_METHOD_ID,
    B1CodexCall,
)
from tracepixel.benchmark.b1_harness import build_b1_schedule, load_b1_preregistration
from tracepixel.benchmark.b1_runner import run_b1_attempt, write_b1_attempt_execution

ROOT = Path(__file__).resolve().parents[1]
B1_PREREGISTRATION = ROOT / "evidence" / "b1" / "preregistration.v1.json"


def _program(pixels: list[list[int]]) -> dict[str, object]:
    return {
        "schema": "tracepixel.pixel-program.v1",
        "canvas": {"width": 16, "height": 16},
        "operations": [] if not pixels else [{"op": "set_pixels", "pixels": pixels}],
    }


def _square_program() -> dict[str, object]:
    pixels = [
        [x, y, 128, 32, 192, 255]
        for y in range(6, 10)
        for x in range(6, 10)
    ]
    return _program(pixels)


def _single_pixel_program() -> dict[str, object]:
    return _program([[7, 7, 128, 32, 192, 255]])


class _FakeExecutor:
    def __init__(self, outputs, *, oversized_input_at: int | None = None) -> None:
        self.outputs = list(outputs)
        self.oversized_input_at = oversized_input_at
        self.requests: list[dict[str, object]] = []

    def invoke(self, request, *, call_index: int) -> B1CodexCall:
        self.requests.append(request)
        program = self.outputs[min(call_index - 1, len(self.outputs) - 1)]
        method_id = request["attempt"]["method_id"]
        output = (
            {
                "schema": "tracepixel.agent-provider-proposal.v1",
                "kind": "pixel_program",
                "payload": program,
            }
            if method_id == B1_TRACEPIXEL_METHOD_ID
            else program
        )
        raw = json.dumps(output, sort_keys=True)
        return B1CodexCall(
            status="response",
            output=output,
            raw_output=raw,
            input_tokens=24001 if call_index == self.oversized_input_at else 100,
            output_tokens=20,
            tool_calls=0,
            wall_time_ms=1,
            returncode=0,
            error_code=None,
        )


class B1S0RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration, digest = load_b1_preregistration(B1_PREREGISTRATION)
        cls.schedule = build_b1_schedule(cls.preregistration, preregistration_sha256=digest)

    def _identity(self, method_id: str):
        return next(
            attempt
            for attempt in self.schedule["attempts"]
            if attempt["method_id"] == method_id and attempt["task_id"] == "B1-T0-01"
        )

    def test_tracepixel_consumes_all_six_stages_even_when_first_artifact_already_passes_qa(self) -> None:
        executor = _FakeExecutor([_square_program()] * 6)
        execution = run_b1_attempt(
            self.preregistration,
            identity=self._identity(B1_TRACEPIXEL_METHOD_ID),
            executor=executor,
            runner_commit="runner-test",
        )

        self.assertTrue(execution.record["completion"])
        self.assertTrue(execution.record["deterministic_qa"]["all_rules_pass"])
        self.assertEqual(execution.record["stage_coverage"]["decided_stages"], 6)
        self.assertEqual(execution.record["stage_coverage"]["applied_stages"], 6)
        self.assertEqual(execution.record["complexity"]["provider_calls"], 6)
        self.assertEqual(
            [request["current_stage"] for request in executor.requests],
            list(B1_STAGE_SEQUENCE_V1),
        )

    def test_zero_edit_authoring_response_is_an_explicit_skip_without_erasing_last_artifact(self) -> None:
        outputs = [_square_program(), _program([]), *([_square_program()] * 4)]
        execution = run_b1_attempt(
            self.preregistration,
            identity=self._identity(B1_TRACEPIXEL_METHOD_ID),
            executor=_FakeExecutor(outputs),
        )

        self.assertTrue(execution.record["completion"])
        self.assertEqual(execution.record["stage_coverage"]["decided_stages"], 6)
        self.assertEqual(execution.record["stage_coverage"]["skipped_stages"], 1)
        self.assertTrue(execution.record["deterministic_qa"]["all_rules_pass"])
        self.assertIn("final.rgba", execution.payloads)

    def test_tracepixel_uses_bounded_post_stage_repair_headroom_only_after_six_decisions(self) -> None:
        executor = _FakeExecutor([*([_single_pixel_program()] * 6), _square_program()])
        execution = run_b1_attempt(
            self.preregistration,
            identity=self._identity(B1_TRACEPIXEL_METHOD_ID),
            executor=executor,
        )

        self.assertTrue(execution.record["completion"])
        self.assertEqual(execution.record["stage_coverage"]["decided_stages"], 6)
        self.assertEqual(execution.record["complexity"]["provider_calls"], 7)
        self.assertEqual(execution.record["complexity"]["repair_cycles"], 1)
        self.assertTrue(execution.record["deterministic_qa"]["all_rules_pass"])
        self.assertTrue(executor.requests[6]["deterministic_feedback"]["available"])
        self.assertEqual(executor.requests[6]["current_stage"], B1_STAGE_SEQUENCE_V1[-1])
        self.assertFalse(execution.record["repair"]["available"])

    def test_raw_baseline_can_stop_on_first_structurally_passing_full_program(self) -> None:
        executor = _FakeExecutor([_square_program()] * 8)
        execution = run_b1_attempt(
            self.preregistration,
            identity=self._identity(B1_RAW_METHOD_ID),
            executor=executor,
        )

        self.assertTrue(execution.record["completion"])
        self.assertEqual(execution.record["complexity"]["provider_calls"], 1)
        self.assertFalse(execution.record["stage_coverage"]["applicable"])
        self.assertIsNone(execution.record["complexity"]["repair_cycles"])
        self.assertNotIn("current_stage", executor.requests[0])

    def test_budget_failure_preserves_the_completed_stage_prefix(self) -> None:
        executor = _FakeExecutor(
            [_single_pixel_program(), _square_program()],
            oversized_input_at=2,
        )
        execution = run_b1_attempt(
            self.preregistration,
            identity=self._identity(B1_TRACEPIXEL_METHOD_ID),
            executor=executor,
        )

        self.assertFalse(execution.record["completion"])
        self.assertEqual(execution.record["failure_category"], "budget_exhaustion")
        self.assertEqual(execution.record["stage_coverage"]["decided_stages"], 1)
        self.assertEqual(execution.record["complexity"]["provider_calls"], 2)
        self.assertNotIn("final.rgba", execution.payloads)

    def test_writer_claims_the_exact_frozen_attempt_root_and_refuses_overwrite(self) -> None:
        execution = run_b1_attempt(
            self.preregistration,
            identity=self._identity(B1_RAW_METHOD_ID),
            executor=_FakeExecutor([_square_program()]),
        )
        with tempfile.TemporaryDirectory() as temporary:
            target = write_b1_attempt_execution(
                temporary,
                self.preregistration,
                execution,
            )
            self.assertTrue((target / "attempt-record.json").is_file())
            self.assertTrue((target / "retention-index.json").is_file())
            self.assertIn(execution.record["attempt"]["freeze_commit"], target.as_posix())
            with self.assertRaises(FileExistsError):
                write_b1_attempt_execution(
                    temporary,
                    self.preregistration,
                    execution,
                )


if __name__ == "__main__":
    unittest.main()
