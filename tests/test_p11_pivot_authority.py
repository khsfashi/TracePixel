from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class P11PivotAuthorityTests(unittest.TestCase):
    def test_core_lane_preserves_p11_history_and_explicit_p12_successor(self) -> None:
        lane = json.loads((ROOT / "config" / "tracepixel.core-lane.json").read_text(encoding="utf-8"))
        p11_children = lane["child_sequences"]["P11"]
        self.assertEqual(
            p11_children,
            ["P11-X0", "P11-X1", "P11-X2", "P11-X3", "P11-B0", "P11-B1", "P11-P0"],
        )
        self.assertEqual(lane["current"], "P12")
        self.assertEqual(lane["current_child"], "P12-R1")
        self.assertEqual(lane["active_issue"], 155)
        self.assertIn("P11", lane["sequence"])
        self.assertIn("P12", lane["sequence"])
        self.assertLess(lane["sequence"].index("P11"), lane["sequence"].index("P12"))
        self.assertEqual(
            lane["child_sequences"]["P12"],
            ["P12-R0", "P12-R1", "P12-R2", "P12-P0"],
        )
        self.assertTrue(any("P11-X0 and P11-X1 are retained useful research" in rule for rule in lane["rules"]))
        self.assertTrue(any("P11-X2, P11-X3, P11-B0, P11-B1 and P11-P0 are superseded" in rule for rule in lane["rules"]))
        self.assertTrue(any("P12-R0 completed" in rule for rule in lane["rules"]))
        self.assertTrue(any("P12-R1 is provider-free and feature-free" in rule for rule in lane["rules"]))

    def test_p12_r0_freezes_responsibility_diff_before_matched_benchmark(self) -> None:
        doc = (ROOT / "docs" / "P12_R0_RESPONSIBILITY_DIFF.md").read_text(encoding="utf-8")
        self.assertIn("Status: **complete / provider-free / feature-free**", doc)
        self.assertIn("Aseprite", doc)
        self.assertIn("ImageMagick", doc)
        self.assertIn("Local rectangular/pixel mutation as a primitive", doc)
        self.assertIn("measurably unique candidate", doc)
        self.assertIn("protected pixel byte-identically", doc)
        self.assertIn("P12-R1 gate", doc)
        self.assertIn("R1 must not execute the matched run", doc)
        self.assertIn("Do **not** create a composite winner score", doc)

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
