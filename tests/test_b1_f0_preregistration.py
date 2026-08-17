from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
B0_FREEZE = ROOT / "evidence" / "b0" / "preregistration.v1.json"
B1_FREEZE = ROOT / "evidence" / "b1" / "preregistration.v1.json"


class B1F0PreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.b0 = json.loads(B0_FREEZE.read_text(encoding="utf-8"))
        cls.b1 = json.loads(B1_FREEZE.read_text(encoding="utf-8"))

    def test_freeze_pins_post_p7_repository_and_matched_methods(self) -> None:
        freeze = self.b1
        self.assertEqual(freeze["schema"], "tracepixel.b1-preregistration.v1")
        self.assertEqual(freeze["benchmark_id"], "B1")
        self.assertEqual(freeze["freeze_status"], "frozen")
        self.assertEqual(
            freeze["repository_commit_under_test"],
            "0ee45b1e466d4d1ec4e077b835ae31d47a1379a1",
        )
        self.assertEqual(
            freeze["predecessor_evidence"]["p7_to_b1_handoff_commit"],
            freeze["repository_commit_under_test"],
        )

        methods = freeze["scored_methods"]
        self.assertEqual(
            [method["id"] for method in methods],
            ["tracepixel-post-p7-v1", "raw-pixel-program-v1"],
        )
        for method in methods:
            self.assertEqual(method["provider_surface"], "openai-codex-cli")
            self.assertEqual(method["provider_auth_mode"], "chatgpt")
            self.assertEqual(method["model"], "gpt-5.6-sol")
            self.assertEqual(method["reasoning_effort"], "low")
            self.assertEqual(method["codex_cli_version"], "codex-cli 0.147.0")
            self.assertFalse(method["vision_input"])
            self.assertTrue(method["ephemeral"])

    def test_tasks_are_new_held_out_t0_to_t3_variants(self) -> None:
        b1_tasks = self.b1["tasks"]
        b0_tasks = self.b0["tasks"]

        self.assertEqual(len(b1_tasks), 7)
        self.assertEqual(
            [task["tier"] for task in b1_tasks],
            ["T0", "T1", "T1", "T2", "T2", "T3", "T3"],
        )
        self.assertEqual(len({task["id"] for task in b1_tasks}), len(b1_tasks))

        b0_ids = {task["id"] for task in b0_tasks}
        b0_visible_texts = {task["visible_text"] for task in b0_tasks}
        self.assertTrue({task["id"] for task in b1_tasks}.isdisjoint(b0_ids))
        self.assertTrue(
            {task["visible_text"] for task in b1_tasks}.isdisjoint(b0_visible_texts)
        )

        for task in b1_tasks:
            self.assertTrue(task["visible_text"])
            constraints = task["hidden_structural_constraints"]
            self.assertEqual(constraints["width"], 16)
            self.assertEqual(constraints["height"], 16)
            self.assertTrue(constraints["transparent_background"])
            self.assertFalse(constraints["edge_contact_allowed"])
            self.assertGreaterEqual(constraints["minimum_margin_each_side"], 1)
            self.assertGreaterEqual(constraints["maximum_visible_colors"], 1)
            self.assertEqual(constraints["connected_components"], 1)
            self.assertEqual(constraints["maximum_isolated_visible_pixels"], 0)

        boundary = self.b1["held_out_boundary"]
        self.assertIn("must not equal any B0 task ID", boundary["selection_rule"])
        self.assertIn("must not read, copy, seed from", boundary["asset_output_rule"])
        self.assertIn("never rerun or relabelled", boundary["no_score_improving_rerun"])

    def test_budget_allows_full_stage_progression_but_stays_bounded(self) -> None:
        budget = self.b1["budgets"]
        self.assertEqual(budget["trials_per_task_per_scored_method"], 2)
        self.assertEqual(budget["max_provider_calls_per_trial"], 8)
        self.assertEqual(budget["max_iterations_per_trial"], 8)
        self.assertEqual(budget["max_tool_calls_per_trial"], 8)
        self.assertEqual(budget["max_operations_per_trial"], 32)
        self.assertEqual(budget["max_pixel_edits_per_trial"], 2048)
        self.assertIn("six staged authoring steps", budget["pixel_edit_budget_semantics"])
        self.assertEqual(budget["max_visual_observation_calls_per_trial"], 0)
        self.assertEqual(budget["human_interventions_during_generation"], 0)
        self.assertGreater(budget["provider_call_timeout_seconds"], 0)
        self.assertGreater(budget["trial_wall_timeout_seconds"], 0)

        scheduled = (
            len(self.b1["tasks"])
            * len(self.b1["scored_methods"])
            * budget["trials_per_task_per_scored_method"]
        )
        self.assertEqual(scheduled, 28)

    def test_stage_repair_complexity_and_authority_layers_stay_separate(self) -> None:
        scoring = self.b1["deterministic_scoring"]
        self.assertIn(
            "explicitly applied or skipped",
            scoring["stage_completion_for_tracepixel"],
        )
        self.assertIn("not folded", scoring["stage_completion_for_tracepixel"])
        self.assertIn("No single winner", scoring["tie_breaking"])

        required = set(self.b1["complexity_reporting"]["required_when_available"])
        for field in {
            "changed_pixels",
            "changed_operations",
            "repair_cycles",
            "authored_stages",
            "skipped_stages",
            "unaffected_region_stability",
        }:
            self.assertIn(field, required)

        matching = self.b1["information_matching"]
        self.assertIn(
            "disabled",
            matching["human_feedback_during_generation"],
        )
        self.assertFalse(matching["external_reference_images"])

    def test_unresolved_owner_gates_and_b0_mutation_remain_out(self) -> None:
        by_family = {
            item["family"]: item for item in self.b1["non_scored_baselines"]
        }
        self.assertEqual(by_family["aseprite-mcp-agent"]["status"], "not-scored")
        self.assertIn("G5", by_family["aseprite-mcp-agent"]["reason"])

        perceptual = self.b1["perceptual_evaluation"]
        self.assertIn("disabled", perceptual["vlm_judge"])
        self.assertIn("G4", perceptual["vlm_judge"])
        self.assertEqual(perceptual["human_evaluator_count"], 1)
        self.assertEqual(perceptual["edits_during_review"], "forbidden")

        execution = self.b1["execution_environment"]
        self.assertFalse(execution["github_self_hosted_runner"])
        self.assertIn("unresolved", execution["g6_status"])

        exclusion = self.b1["exclusion_policy"]
        self.assertIn("Forbidden", exclusion["cross_cohort_substitution"])

        retention = self.b1["artifact_retention"]
        self.assertTrue(retention["retain_every_scheduled_attempt"])
        self.assertIn("never replaced", retention["unsuccessful_attempts"])
        self.assertIn("No retained B1 attempt file", retention["b0_separation"])

        immutability = self.b1["immutability"]
        self.assertIn("never mutated, rerun, rescored", immutability["b0_boundary"])
        self.assertIn("after B1-P0", immutability["p8_boundary"])


if __name__ == "__main__":
    unittest.main()
