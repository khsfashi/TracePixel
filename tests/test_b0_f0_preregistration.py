from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "evidence" / "b0" / "preregistration.v1.json"


class B0F0PreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.freeze = json.loads(FREEZE.read_text(encoding="utf-8"))

    def test_freeze_has_exact_initial_cohort_identity(self) -> None:
        freeze = self.freeze
        self.assertEqual(freeze["schema"], "tracepixel.b0-preregistration.v1")
        self.assertEqual(freeze["benchmark_id"], "B0")
        self.assertEqual(freeze["freeze_status"], "frozen")
        self.assertEqual(
            freeze["repository_commit_under_test"],
            "7fd1a3a0f952203d1875e802c89c3ab6e3750611",
        )

        methods = freeze["scored_methods"]
        self.assertEqual(
            [method["id"] for method in methods],
            ["tracepixel-staged-v1", "raw-pixel-program-v1"],
        )
        for method in methods:
            self.assertEqual(method["provider_surface"], "openai-codex-cli")
            self.assertEqual(method["provider_auth_mode"], "chatgpt")
            self.assertEqual(method["model"], "gpt-5.6-sol")
            self.assertEqual(method["reasoning_effort"], "low")
            self.assertEqual(method["codex_cli_version"], "codex-cli 0.147.0")
            self.assertFalse(method["vision_input"])
            self.assertTrue(method["ephemeral"])

    def test_tasks_are_small_visible_t0_to_t3_and_structurally_closed(self) -> None:
        tasks = self.freeze["tasks"]
        self.assertEqual(len(tasks), 7)
        self.assertEqual(
            [task["tier"] for task in tasks],
            ["T0", "T1", "T1", "T2", "T2", "T3", "T3"],
        )
        self.assertEqual(len({task["id"] for task in tasks}), len(tasks))

        for task in tasks:
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

    def test_budget_and_trials_are_finite_and_allow_bounded_revision_headroom(self) -> None:
        budget = self.freeze["budgets"]
        self.assertEqual(budget["trials_per_task_per_scored_method"], 2)
        self.assertEqual(budget["max_provider_calls_per_trial"], 4)
        self.assertEqual(budget["max_iterations_per_trial"], 4)
        self.assertEqual(budget["max_tool_calls_per_trial"], 4)
        self.assertEqual(budget["max_operations_per_trial"], 16)
        self.assertEqual(budget["max_pixel_edits_per_trial"], 1024)
        self.assertIn("Cumulative", budget["pixel_edit_budget_semantics"])
        self.assertEqual(budget["max_visual_observation_calls_per_trial"], 0)
        self.assertEqual(budget["human_interventions_during_generation"], 0)
        self.assertGreater(budget["provider_call_timeout_seconds"], 0)
        self.assertGreater(budget["trial_wall_timeout_seconds"], 0)

        scheduled = (
            len(self.freeze["tasks"])
            * len(self.freeze["scored_methods"])
            * budget["trials_per_task_per_scored_method"]
        )
        self.assertEqual(scheduled, 28)

    def test_unresolved_owner_gates_are_not_silently_crossed(self) -> None:
        by_family = {
            item["family"]: item for item in self.freeze["non_scored_baselines"]
        }
        self.assertEqual(by_family["aseprite-mcp-agent"]["status"], "not-scored")
        self.assertIn("G5", by_family["aseprite-mcp-agent"]["reason"])

        perceptual = self.freeze["perceptual_evaluation"]
        self.assertIn("disabled", perceptual["vlm_judge"])
        self.assertIn("G4", perceptual["vlm_judge"])
        self.assertEqual(perceptual["human_evaluator_count"], 1)

        execution = self.freeze["execution_environment"]
        self.assertFalse(execution["github_self_hosted_runner"])
        self.assertIn("unresolved", execution["g6_status"])

    def test_failures_and_unsuccessful_attempts_cannot_be_cherry_picked(self) -> None:
        exclusion = self.freeze["exclusion_policy"]
        self.assertIn("No scored attempt is excluded", exclusion["after_provider_invocation"])
        self.assertIn("Forbidden", exclusion["task_relabeling"])

        retry = self.freeze["retry_policy"]
        self.assertEqual(retry["semantic_retry_after_valid_provider_response"], 0)
        self.assertEqual(retry["budget_exhaustion_retry"], 0)
        self.assertEqual(retry["manual_repair_retry"], 0)

        retention = self.freeze["artifact_retention"]
        self.assertTrue(retention["retain_every_scheduled_attempt"])
        self.assertIn("never replaced", retention["unsuccessful_attempts"])

        scoring = self.freeze["deterministic_scoring"]
        self.assertIn("Failed/non-completing trials remain in denominators", scoring["aggregation"])
        self.assertIn("No single winner", scoring["tie_breaking"])


if __name__ == "__main__":
    unittest.main()
