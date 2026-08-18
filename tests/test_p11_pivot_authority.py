from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class P11PivotAuthorityTests(unittest.TestCase):
    def test_core_lane_points_to_p11_x0(self) -> None:
        lane = json.loads((ROOT / "config" / "tracepixel.core-lane.json").read_text(encoding="utf-8"))
        self.assertEqual(lane["current"], "P11")
        self.assertEqual(lane["current_child"], "P11-X0")
        self.assertEqual(lane["active_issue"], 151)
        self.assertEqual(
            lane["child_sequences"]["P11"],
            ["P11-X0", "P11-X1", "P11-X2", "P11-X3", "P11-B0", "P11-B1", "P11-P0"],
        )

    def test_owner_review_loop_requires_explicit_human_aesthetic_authority(self) -> None:
        policy = json.loads(
            (ROOT / "config" / "tracepixel.owner-review-loop.json").read_text(encoding="utf-8")
        )
        review = policy["owner_review"]
        self.assertEqual(review["final_aesthetic_authority"], "repository-owner")
        self.assertFalse(review["deterministic_qa_can_auto_accept_aesthetics"])
        self.assertFalse(review["vlm_can_auto_accept_aesthetics"])
        self.assertEqual(review["unspecified_criterion_status"], "unresolved")
        self.assertTrue(review["natural_language_feedback_allowed"])
        self.assertFalse(review["manual_json_required"])

    def test_retry_policy_forbids_score_until_threshold_and_preserves_rejects(self) -> None:
        policy = json.loads(
            (ROOT / "config" / "tracepixel.owner-review-loop.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            policy["retry_policy"]["aesthetic_score_until_threshold_loop"],
            "forbidden",
        )
        self.assertTrue(policy["retry_policy"]["provider_retry_requires_preregistered_budget"])
        self.assertTrue(policy["retry_policy"]["provider_budget_may_not_expand_after_result_seen"])
        self.assertTrue(policy["evidence_policy"]["retain_rejected_results"])
        self.assertFalse(policy["evidence_policy"]["overwrite_negative_evidence"])
        self.assertTrue(policy["evidence_policy"]["separate_quality_and_cost"])

    def test_pivot_document_keeps_direct_authoring_optional_not_privileged(self) -> None:
        doc = (ROOT / "docs" / "P11_GENERATOR_NEUTRAL_PIVOT.md").read_text(encoding="utf-8")
        self.assertIn("TracePixel-direct is not deleted", doc)
        self.assertIn("It is **not** privileged", doc)
        self.assertIn("awaiting-owner-review", doc)
        self.assertIn("Do **not** implement", doc)
        self.assertIn("while aesthetic_score < threshold", doc)


if __name__ == "__main__":
    unittest.main()
