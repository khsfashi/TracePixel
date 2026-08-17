from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest

from tracepixel.benchmark.b1_adapters import (
    B1_RAW_METHOD_ID,
    B1_STAGE_SEQUENCE_V1,
    B1_TRACEPIXEL_METHOD_ID,
    B1AdapterContractError,
    B1CodexExecutor,
    b1_provider_output_schema,
    build_b1_codex_exec_plan,
    build_b1_method_adapter,
    build_b1_provider_request,
    normalize_b1_provider_output,
    render_b1_codex_prompt,
    validate_b1_scored_methods,
)
from tracepixel.benchmark.b1_harness import (
    B1_FREEZE_COMMIT,
    build_b1_schedule,
    load_b1_preregistration,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "evidence" / "b1" / "preregistration.v1.json"


class B1S0AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.freeze, digest = load_b1_preregistration(FREEZE)
        cls.schedule = build_b1_schedule(cls.freeze, preregistration_sha256=digest)

    def _identity(self, method_id: str):
        return next(
            attempt
            for attempt in self.schedule["attempts"]
            if attempt["method_id"] == method_id
        )

    def test_frozen_method_order_and_provider_settings_are_pinned(self) -> None:
        tracepixel, raw = validate_b1_scored_methods(self.freeze)
        self.assertEqual(tracepixel["id"], B1_TRACEPIXEL_METHOD_ID)
        self.assertEqual(raw["id"], B1_RAW_METHOD_ID)
        fields = (
            "provider_surface",
            "provider_auth_mode",
            "model",
            "reasoning_effort",
            "vision_input",
            "codex_cli_version",
            "sandbox",
            "ephemeral",
        )
        self.assertEqual(
            {field: tracepixel[field] for field in fields},
            {field: raw[field] for field in fields},
        )

        drifted = deepcopy(self.freeze)
        drifted["scored_methods"][1]["model"] = "different-model"
        with self.assertRaises(B1AdapterContractError) as caught:
            validate_b1_scored_methods(drifted)
        self.assertEqual(caught.exception.code, "provider_contract_drift")

    def test_paired_requests_share_visible_information_without_hidden_or_b0_results(self) -> None:
        tracepixel_identity = self._identity(B1_TRACEPIXEL_METHOD_ID)
        raw_identity = next(
            attempt
            for attempt in self.schedule["attempts"]
            if attempt["method_id"] == B1_RAW_METHOD_ID
            and attempt["task_id"] == tracepixel_identity["task_id"]
            and attempt["trial_index"] == tracepixel_identity["trial_index"]
        )
        tracepixel = build_b1_provider_request(
            self.freeze,
            identity=tracepixel_identity,
        )
        raw = build_b1_provider_request(self.freeze, identity=raw_identity)

        self.assertEqual(tracepixel["visible_task"], raw["visible_task"])
        self.assertEqual(tracepixel["provider"], raw["provider"])
        self.assertEqual(tracepixel["matched_budget"], raw["matched_budget"])
        for request in (tracepixel, raw):
            encoded = json.dumps(request, sort_keys=True)
            self.assertNotIn("hidden_structural_constraints", encoded)
            self.assertNotIn("evidence/b0/results/", encoded.lower())

    def test_tracepixel_surface_exposes_six_stages_and_bounded_repair_only(self) -> None:
        tracepixel = build_b1_method_adapter(self.freeze, B1_TRACEPIXEL_METHOD_ID)
        raw = build_b1_method_adapter(self.freeze, B1_RAW_METHOD_ID)

        self.assertEqual(
            tracepixel["authoring_surface"]["stage_sequence"],
            list(B1_STAGE_SEQUENCE_V1),
        )
        self.assertEqual(len(B1_STAGE_SEQUENCE_V1), 6)
        self.assertTrue(tracepixel["authoring_surface"]["stage_guidance"])
        self.assertEqual(
            tracepixel["authoring_surface"]["repair_surface"]["kind"],
            "p7-bounded-deterministic-repair",
        )
        self.assertFalse(
            tracepixel["authoring_surface"]["repair_surface"][
                "human_feedback_during_generation"
            ]
        )
        self.assertNotIn("stage_sequence", raw["authoring_surface"])
        self.assertNotIn("repair_surface", raw["authoring_surface"])

        with self.assertRaises(B1AdapterContractError) as caught:
            build_b1_provider_request(
                self.freeze,
                identity=self._identity(B1_RAW_METHOD_ID),
                current_stage="silhouette",
            )
        self.assertEqual(caught.exception.code, "raw_stage_guidance_forbidden")

    def test_all_28_frozen_attempts_materialize_codex_plans_without_provider_calls(self) -> None:
        plans = []
        for identity in self.schedule["attempts"]:
            request = build_b1_provider_request(self.freeze, identity=identity)
            prompt = render_b1_codex_prompt(request)
            plan = build_b1_codex_exec_plan(request)
            plans.append(plan)

            self.assertIn(request["visible_task"]["visible_text"], prompt)
            self.assertNotIn("hidden_structural_constraints", prompt)
            self.assertNotIn("evidence/b0/results/", prompt.lower())
            self.assertEqual(plan["timeout_seconds"], 180)
            self.assertEqual(plan["expected_version"], "codex-cli 0.147.0")
            self.assertEqual(plan["required_auth_marker"], "Logged in using ChatGPT")
            self.assertTrue(plan["forbid_api_key_auth"])
            self.assertIn("--sandbox", plan["command"])
            self.assertIn("read-only", plan["command"])
            self.assertIn("gpt-5.6-sol", plan["command"])
            self.assertTrue(
                plan["retention_relative_path"].startswith(
                    f"evidence/b1/results/{B1_FREEZE_COMMIT}/"
                )
            )
            self.assertNotIn("/b0/", plan["retention_relative_path"].lower())

        self.assertEqual(len(plans), 28)
        self.assertEqual(len({plan["retention_relative_path"] for plan in plans}), 28)

    def test_output_shapes_normalize_to_the_same_pixel_program_surface(self) -> None:
        program = {
            "schema": "tracepixel.pixel-program.v1",
            "canvas": {"width": 16, "height": 16},
            "operations": [
                {"op": "set_pixels", "pixels": [[7, 7, 0, 255, 255, 255]]}
            ],
        }
        tracepixel_output = {
            "schema": "tracepixel.agent-provider-proposal.v1",
            "kind": "pixel_program",
            "payload": program,
        }
        self.assertEqual(
            normalize_b1_provider_output(B1_TRACEPIXEL_METHOD_ID, tracepixel_output),
            program,
        )
        self.assertEqual(
            normalize_b1_provider_output(B1_RAW_METHOD_ID, program),
            program,
        )
        self.assertEqual(
            b1_provider_output_schema(B1_TRACEPIXEL_METHOD_ID)["properties"]["kind"][
                "const"
            ],
            "pixel_program",
        )
        self.assertEqual(
            b1_provider_output_schema(B1_RAW_METHOD_ID)["properties"]["schema"][
                "const"
            ],
            "tracepixel.pixel-program.v1",
        )

    def test_provider_visible_b0_result_reference_is_rejected(self) -> None:
        drifted = deepcopy(self.freeze)
        drifted["tasks"][0]["visible_text"] += " seed evidence/b0/results/old/output.json"
        with self.assertRaises(B1AdapterContractError) as caught:
            build_b1_provider_request(
                drifted,
                identity=self.schedule["attempts"][0],
            )
        self.assertEqual(caught.exception.code, "b0_result_reference")

    def test_executor_preflight_requires_exact_codex_version_and_chatgpt_auth(self) -> None:
        request = build_b1_provider_request(
            self.freeze,
            identity=self._identity(B1_RAW_METHOD_ID),
        )

        def fake_run(command, **kwargs):
            del kwargs
            if "--version" in command:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="codex-cli 0.147.0\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="Logged in using ChatGPT\n",
                stderr="",
            )

        executor = B1CodexExecutor(
            _run=fake_run,
            _which=lambda _: "/fake/codex",
        )
        environment = executor.preflight(request)
        self.assertEqual(environment["auth_mode"], "chatgpt")
        self.assertEqual(environment["model"], "gpt-5.6-sol")
        self.assertEqual(environment["codex_cli_version"], "codex-cli 0.147.0")

        def api_key_run(command, **kwargs):
            del kwargs
            if "--version" in command:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="codex-cli 0.147.0\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="Logged in using ChatGPT\nLogged in using an API key\n",
                stderr="",
            )

        with self.assertRaises(B1AdapterContractError) as caught:
            B1CodexExecutor(
                _run=api_key_run,
                _which=lambda _: "/fake/codex",
            ).preflight(request)
        self.assertEqual(caught.exception.code, "api_key_auth_forbidden")

    def test_executor_invocation_retains_usage_and_never_reads_b0_output(self) -> None:
        request = build_b1_provider_request(
            self.freeze,
            identity=self._identity(B1_RAW_METHOD_ID),
        )
        program = {
            "schema": "tracepixel.pixel-program.v1",
            "canvas": {"width": 16, "height": 16},
            "operations": [
                {"op": "set_pixels", "pixels": [[7, 7, 20, 30, 40, 255]]}
            ],
        }
        seen_prompts: list[str] = []

        def fake_run(command, **kwargs):
            prompt = kwargs.get("input")
            self.assertIsInstance(prompt, str)
            seen_prompts.append(prompt)
            output_index = command.index("--output-last-message") + 1
            output_path = Path(command[output_index])
            output_path.write_text(json.dumps(program), encoding="utf-8")
            stdout = "\n".join(
                (
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {"type": "command_execution"},
                        }
                    ),
                    json.dumps(
                        {
                            "type": "turn.completed",
                            "usage": {"input_tokens": 123, "output_tokens": 45},
                        }
                    ),
                )
            )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=stdout,
                stderr="",
            )

        call = B1CodexExecutor(
            _run=fake_run,
            _which=lambda _: "/fake/codex",
        ).invoke(request, call_index=1)
        self.assertEqual(call.status, "response")
        self.assertEqual(call.output, program)
        self.assertEqual(call.input_tokens, 123)
        self.assertEqual(call.output_tokens, 45)
        self.assertEqual(call.tool_calls, 1)
        self.assertEqual(call.returncode, 0)
        self.assertEqual(len(seen_prompts), 1)
        self.assertNotIn("evidence/b0/results/", seen_prompts[0].lower())


if __name__ == "__main__":
    unittest.main()
