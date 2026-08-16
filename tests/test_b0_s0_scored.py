from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from typing import cast

from tracepixel.benchmark import (
    B0CodexCall,
    B0CodexExecutor,
    B0_RAW_METHOD_ID,
    B0_TRACEPIXEL_METHOD_ID,
    b0_feedback_from_qa,
    build_b0_provider_request,
    build_b0_schedule,
    load_b0_preregistration,
    run_b0_attempt,
    score_b0_canvas,
)
from tracepixel.model import execute_pixel_program
from evidence.b0_s0.run import _claim_attempt, _reconcile_claims


ROOT = Path(__file__).parents[1]
PREREGISTRATION = ROOT / "evidence" / "b0" / "preregistration.v1.json"


def diamond_program() -> dict[str, object]:
    pixels: list[list[int]] = []
    spans = ((4, 7, 8), (5, 6, 9), (6, 5, 10), (7, 4, 11), (8, 4, 11), (9, 5, 10), (10, 6, 9), (11, 7, 8))
    for y, start, end in spans:
        for x in range(start, end + 1):
            pixels.append([x, y, 0, 220, 255, 255])
    return {
        "schema": "tracepixel.pixel-program.v1",
        "canvas": {"width": 16, "height": 16},
        "operations": [{"op": "set_pixels", "pixels": pixels}],
    }


class SequenceExecutor:
    def __init__(self, calls: list[B0CodexCall]) -> None:
        self.calls = list(calls)
        self.requests: list[object] = []

    def invoke(self, request, *, call_index: int) -> B0CodexCall:
        del call_index
        self.requests.append(request)
        return self.calls.pop(0)


class B0S0ScoredTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration, digest = load_b0_preregistration(PREREGISTRATION)
        cls.schedule = build_b0_schedule(cls.preregistration, preregistration_sha256=digest)
        cls.program = diamond_program()

    def identity(self, method_id: str):
        return next(
            item
            for item in self.schedule["attempts"]
            if item["task_id"] == "B0-T0-01" and item["method_id"] == method_id and item["trial_index"] == 1
        )

    def output(self, method_id: str) -> object:
        if method_id == B0_TRACEPIXEL_METHOD_ID:
            return {"schema": "tracepixel.agent-provider-proposal.v1", "kind": "pixel_program", "payload": self.program}
        return self.program

    def success_call(self, method_id: str) -> B0CodexCall:
        output = self.output(method_id)
        return B0CodexCall("response", output, json.dumps(output), 100, 50, 0, 2, 0, None)

    def test_scoring_all_pass_diamond(self) -> None:
        qa = score_b0_canvas(self.preregistration, "B0-T0-01", execute_pixel_program(self.program))
        self.assertTrue(qa["all_rules_pass"])
        self.assertTrue(all(cast(dict[str, bool], qa["rule_results"]).values()))
        feedback = b0_feedback_from_qa(qa)
        self.assertTrue(feedback["available"])
        self.assertEqual([], feedback["findings"])

    def test_feedback_exposes_actual_facts_without_hidden_expected_values(self) -> None:
        empty = {
            "schema": "tracepixel.pixel-program.v1",
            "canvas": {"width": 16, "height": 16},
            "operations": [],
        }
        qa = score_b0_canvas(self.preregistration, "B0-T0-01", execute_pixel_program(empty))
        feedback = b0_feedback_from_qa(qa)
        self.assertTrue(feedback["findings"])
        self.assertNotIn("expected", json.dumps(feedback, sort_keys=True))

    def test_changed_pixel_metric_becomes_unavailable_across_dimension_change(self) -> None:
        from tracepixel.benchmark import changed_pixel_count

        self.assertIsNone(changed_pixel_count(bytes(4), bytes(8)))

    def test_durable_invocation_claim_blocks_automatic_rerun_without_manifest(self) -> None:
        identity = self.identity(B0_RAW_METHOD_ID)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim = _claim_attempt(root, identity, "4" * 40)
            self.assertTrue(claim.is_file())
            with self.assertRaises(SystemExit):
                _reconcile_claims(root, self.schedule)
            self.assertTrue(claim.is_file())

    def test_both_methods_accept_same_raster_and_keep_hidden_constraints_out_of_request(self) -> None:
        for method_id in (B0_TRACEPIXEL_METHOD_ID, B0_RAW_METHOD_ID):
            identity = self.identity(method_id)
            executor = SequenceExecutor([self.success_call(method_id)])
            execution = run_b0_attempt(
                self.preregistration,
                identity=identity,
                executor=executor,
                runner_commit="1" * 40,
            )
            self.assertTrue(execution.result["completion"])
            self.assertTrue(execution.result["structural"]["all_rules_pass"])
            self.assertEqual(1, execution.result["telemetry"]["provider_calls"])
            self.assertNotIn("hidden_structural_constraints", json.dumps(executor.requests, sort_keys=True))

    def test_transport_retry_is_identical_and_counts_against_provider_budget(self) -> None:
        method_id = B0_RAW_METHOD_ID
        timeout = B0CodexCall("timeout", None, None, None, None, None, 1, None, "codex_timeout")
        executor = SequenceExecutor([timeout, self.success_call(method_id)])
        execution = run_b0_attempt(
            self.preregistration,
            identity=self.identity(method_id),
            executor=executor,
            runner_commit="2" * 40,
        )
        self.assertTrue(execution.result["completion"])
        self.assertEqual(2, execution.result["telemetry"]["provider_calls"])
        self.assertEqual(1, execution.result["telemetry"]["iterations"])
        self.assertEqual(executor.requests[0], executor.requests[1])

    def test_invalid_provider_json_is_noncompletion_and_scores_zero(self) -> None:
        invalid = B0CodexCall("response", None, "not-json", 10, 4, 0, 1, 0, None)
        executor = SequenceExecutor([invalid])
        execution = run_b0_attempt(
            self.preregistration,
            identity=self.identity(B0_RAW_METHOD_ID),
            executor=executor,
            runner_commit="3" * 40,
        )
        self.assertFalse(execution.result["completion"])
        self.assertEqual("invalid_operation_or_ir", execution.result["failure_category"])
        self.assertEqual(0, execution.result["structural"]["passed_rules"])
        self.assertNotIn("final.png", execution.payloads)

    def test_codex_preflight_requires_exact_frozen_version_and_chatgpt_login(self) -> None:
        def fake_run(command, **kwargs):
            del kwargs
            if "--version" in command:
                return subprocess.CompletedProcess(command, 0, stdout="codex-cli 0.147.0\n", stderr="")
            return subprocess.CompletedProcess(command, 0, stdout="Logged in using ChatGPT\n", stderr="")

        executor = B0CodexExecutor(_run=fake_run, _which=lambda _: "/usr/bin/codex")
        request = build_b0_provider_request(self.preregistration, identity=self.identity(B0_TRACEPIXEL_METHOD_ID))
        environment = executor.preflight(request)
        self.assertEqual("codex-cli 0.147.0", environment["codex_cli_version"])
        self.assertEqual("chatgpt", environment["auth_mode"])

    def test_codex_invoke_retains_schema_output_and_usage_without_stderr(self) -> None:
        output = self.output(B0_RAW_METHOD_ID)

        def fake_run(command, **kwargs):
            if "--version" in command:
                return subprocess.CompletedProcess(command, 0, stdout="codex-cli 0.147.0\n", stderr="")
            if "login" in command and "status" in command:
                return subprocess.CompletedProcess(command, 0, stdout="Logged in using ChatGPT\n", stderr="")
            output_index = command.index("--output-last-message") + 1
            Path(command[output_index]).write_text(json.dumps(output), encoding="utf-8")
            stdout = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 7}}) + "\n"
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="local/private/path")

        executor = B0CodexExecutor(_run=fake_run, _which=lambda _: "/usr/bin/codex")
        request = build_b0_provider_request(self.preregistration, identity=self.identity(B0_RAW_METHOD_ID))
        executor.preflight(request)
        call = executor.invoke(request, call_index=1)
        self.assertEqual("response", call.status)
        self.assertEqual(output, call.output)
        self.assertEqual(12, call.input_tokens)
        self.assertEqual(7, call.output_tokens)
        self.assertNotIn("local/private/path", json.dumps(call.record(1)))


if __name__ == "__main__":
    unittest.main()
