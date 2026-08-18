from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class P11PivotAuthorityTests(unittest.TestCase):
    def test_core_lane_preserves_history_and_archived_disposition(self) -> None:
        lane = json.loads((ROOT / "config" / "tracepixel.core-lane.json").read_text(encoding="utf-8"))
        p11_children = lane["child_sequences"]["P11"]
        self.assertEqual(
            p11_children,
            ["P11-X0", "P11-X1", "P11-X2", "P11-X3", "P11-B0", "P11-B1", "P11-P0"],
        )
        self.assertEqual(lane["status"], "archived")
        self.assertEqual(lane["disposition"], "research-complete")
        self.assertEqual(lane["current"], "ARCHIVED")
        self.assertEqual(lane["current_child"], "NONE")
        self.assertIsNone(lane["active_issue"])
        self.assertEqual(lane["archive_issue"], 155)
        self.assertIn("P11", lane["sequence"])
        self.assertIn("P12", lane["sequence"])
        self.assertEqual(lane["sequence"][-1], "ARCHIVED")
        self.assertEqual(
            lane["child_sequences"]["P12"],
            ["P12-R0", "P12-R1", "P12-R2", "P12-P0"],
        )
        self.assertEqual(lane["product_successor"]["repository"], "khsfashi/Trace2D")
        self.assertEqual(lane["product_successor"]["issue"], 318)
        self.assertTrue(any("generic next-task request must not create" in rule for rule in lane["rules"]))
        self.assertTrue(any("P12 precision-edit research is terminated" in rule for rule in lane["rules"]))

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

    def test_pivot_document_remains_historical_evidence(self) -> None:
        doc = (ROOT / "docs" / "P11_GENERATOR_NEUTRAL_PIVOT.md").read_text(encoding="utf-8")
        self.assertIn("TracePixel-direct is not deleted", doc)
        self.assertIn("It is **not** privileged", doc)
        self.assertIn("awaiting-owner-review", doc)
        self.assertIn("Do **not** implement", doc)
        self.assertIn("while aesthetic_score < threshold", doc)

    def test_archive_document_forbids_automatic_reactivation(self) -> None:
        doc = (ROOT / "docs" / "ARCHIVE.md").read_text(encoding="utf-8")
        self.assertIn("ARCHIVED / RESEARCH COMPLETE", doc)
        self.assertIn("Trace2D Asset Studio", doc)
        self.assertIn("must not reopen", doc)
        self.assertIn("No P12-R1/R2 provider run", doc)


if __name__ == "__main__":
    unittest.main()
