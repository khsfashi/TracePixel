from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tracepixel.benchmark import (
    B0AdapterContractError,
    B0_RAW_METHOD_ID,
    B0_STAGE_SEQUENCE_V1,
    B0_TRACEPIXEL_METHOD_ID,
    build_b0_codex_exec_plan,
    build_b0_method_adapter,
    build_b0_provider_request,
    build_b0_schedule,
    b0_provider_output_schema,
    load_b0_preregistration,
    normalize_b0_provider_output,
    render_b0_codex_prompt,
    validate_b0_scored_methods,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "evidence" / "b0" / "preregistration.v1.json"


class B0B0AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.freeze, digest = load_b0_preregistration(FREEZE)
        cls.schedule = build_b0_schedule(cls.freeze, preregistration_sha256=digest)

    def _identity(self, method_id: str):
        return next(attempt for attempt in self.schedule["attempts"] if attempt["method_id"] == method_id)

    def test_frozen_method_order_and_provider_settings_are_pinned(self) -> None:
        staged, raw = validate_b0_scored_methods(self.freeze)
        self.assertEqual(staged["id"], B0_TRACEPIXEL_METHOD_ID)
        self.assertEqual(raw["id"], B0_RAW_METHOD_ID)
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
        self.assertEqual({field: staged[field] for field in fields}, {field: raw[field] for field in fields})

        drifted = deepcopy(self.freeze)
        drifted["scored_methods"][1]["model"] = "different-model"
        with self.assertRaises(B0AdapterContractError):
            validate_b0_scored_methods(drifted)

    def test_requests_share_visible_task_provider_and_budget_without_hidden_constraints(self) -> None:
        staged_identity = self._identity(B0_TRACEPIXEL_METHOD_ID)
        raw_identity = next(
            attempt
            for attempt in self.schedule["attempts"]
            if attempt["method_id"] == B0_RAW_METHOD_ID
            and attempt["task_id"] == staged_identity["task_id"]
            and attempt["trial_index"] == staged_identity["trial_index"]
        )
        staged = build_b0_provider_request(self.freeze, identity=staged_identity)
        raw = build_b0_provider_request(self.freeze, identity=raw_identity)

        self.assertEqual(staged["visible_task"], raw["visible_task"])
        self.assertEqual(staged["provider"], raw["provider"])
        self.assertEqual(staged["matched_budget"], raw["matched_budget"])
        self.assertNotIn("hidden_structural_constraints", json.dumps(staged, sort_keys=True))
        self.assertNotIn("hidden_structural_constraints", json.dumps(raw, sort_keys=True))

    def test_staged_surface_exposes_stage_while_raw_surface_forbids_it(self) -> None:
        staged_adapter = build_b0_method_adapter(self.freeze, B0_TRACEPIXEL_METHOD_ID)
        raw_adapter = build_b0_method_adapter(self.freeze, B0_RAW_METHOD_ID)
        self.assertTrue(staged_adapter["authoring_surface"]["stage_guidance"])
        self.assertEqual(staged_adapter["authoring_surface"]["stage_sequence"], list(B0_STAGE_SEQUENCE_V1))
        self.assertEqual(staged_adapter["authoring_surface"]["art_intent_schema"], "tracepixel.art-intent.v1")
        self.assertEqual(
            set(raw_adapter["authoring_surface"]),
            {
                "visible_task_schema",
                "pixel_program_schema",
                "operation_vocabulary",
                "deterministic_feedback_schema",
                "kind",
            },
        )
        self.assertEqual(raw_adapter["authoring_surface"]["kind"], "raw-pixel-program")

        staged_request = build_b0_provider_request(
            self.freeze, identity=self._identity(B0_TRACEPIXEL_METHOD_ID)
        )
        art_intent = staged_request["method_context"]["art_intent"]
        self.assertEqual(art_intent["canvas"], {"width": 16, "height": 16})
        self.assertIsNone(art_intent["composition"]["occupied_bounds"])
        self.assertIsNone(art_intent["composition"]["light_direction"])

        raw_identity = self._identity(B0_RAW_METHOD_ID)
        with self.assertRaises(B0AdapterContractError):
            build_b0_provider_request(self.freeze, identity=raw_identity, current_stage="silhouette")

    def test_all_28_requests_are_materializable_without_provider_calls(self) -> None:
        requests = [build_b0_provider_request(self.freeze, identity=identity) for identity in self.schedule["attempts"]]
        self.assertEqual(len(requests), 28)
        self.assertEqual(sum("current_stage" in request for request in requests), 14)
        self.assertEqual(sum("current_stage" not in request for request in requests), 14)
        for request in requests:
            prompt = render_b0_codex_prompt(request)
            self.assertIn(request["visible_task"]["visible_text"], prompt)
            self.assertNotIn("hidden_structural_constraints", prompt)
            if request["attempt"]["method_id"] == B0_RAW_METHOD_ID:
                self.assertNotIn("ArtIntent", prompt)
                self.assertNotIn("current_stage", prompt)
                self.assertNotIn("method_context", prompt)
                self.assertNotIn("stage_sequence", prompt)
                self.assertNotIn("stage_guidance", prompt)
            plan = build_b0_codex_exec_plan(request)
            self.assertEqual(plan["timeout_seconds"], 180)
            self.assertEqual(plan["expected_version"], "codex-cli 0.147.0")
            self.assertEqual(plan["required_auth_marker"], "Logged in using ChatGPT")
            self.assertTrue(plan["forbid_api_key_auth"])
            self.assertIn("--sandbox", plan["command"])
            self.assertIn("read-only", plan["command"])
            self.assertIn("gpt-5.6-sol", plan["command"])

    def test_output_shapes_normalize_to_the_same_pixel_program_surface(self) -> None:
        program = {
            "schema": "tracepixel.pixel-program.v1",
            "canvas": {"width": 16, "height": 16},
            "operations": [{"op": "set_pixels", "pixels": [[7, 7, 0, 255, 255, 255]]}],
        }
        staged_output = {
            "schema": "tracepixel.agent-provider-proposal.v1",
            "kind": "pixel_program",
            "payload": program,
        }
        self.assertEqual(normalize_b0_provider_output(B0_TRACEPIXEL_METHOD_ID, staged_output), program)
        self.assertEqual(normalize_b0_provider_output(B0_RAW_METHOD_ID, program), program)
        self.assertEqual(b0_provider_output_schema(B0_TRACEPIXEL_METHOD_ID)["properties"]["kind"]["const"], "pixel_program")
        self.assertEqual(b0_provider_output_schema(B0_RAW_METHOD_ID)["properties"]["schema"]["const"], "tracepixel.pixel-program.v1")

        with self.assertRaises(B0AdapterContractError):
            normalize_b0_provider_output(B0_TRACEPIXEL_METHOD_ID, program)


if __name__ == "__main__":
    unittest.main()
