from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from evidence.b1_s0.review import (
    ReviewContractError,
    load_review_manifest,
    owner_review_summary,
    validate_owner_review,
)

FREEZE = "ca612a026ff5e74c397d9aa4ef8c0bdb25d1df6a"
OWNER = Path("evidence/b1/review") / FREEZE / "owner-review.json"
SUMMARY = Path("evidence/b1/review") / FREEZE / "owner-review-summary.json"


class B1OwnerReviewTests(unittest.TestCase):
    def test_b1_owner_review_is_bound_to_frozen_blind_manifest(self) -> None:
        payload = json.loads(OWNER.read_text(encoding="utf-8"))
        manifest, manifest_sha = load_review_manifest()
        self.assertEqual(manifest_sha, "d51aa6a4ad264ef52a473c74810c416c98caefe466ab19eca2a0d60792dfe419")
        ratings, mapping = validate_owner_review(payload, manifest, manifest_sha)
        self.assertEqual(len(ratings), 28)
        self.assertEqual(len(mapping), 28)
        summary = owner_review_summary(ratings, mapping)
        self.assertEqual(summary, json.loads(SUMMARY.read_text(encoding="utf-8")))
        methods = {item["method_id"]: item for item in summary["methods"]}
        self.assertEqual(methods["raw-pixel-program-v1"]["human_rejection_count"], 1)
        self.assertEqual(methods["raw-pixel-program-v1"]["mean"]["recognizability"], 4.0)
        self.assertEqual(methods["raw-pixel-program-v1"]["mean"]["readability_at_native_1x"], 4.0)
        self.assertEqual(methods["raw-pixel-program-v1"]["mean"]["style_coherence"], 3.9285714285714284)
        self.assertEqual(methods["tracepixel-post-p7-v1"]["human_rejection_count"], 0)
        self.assertEqual(methods["tracepixel-post-p7-v1"]["mean"]["recognizability"], 4.0)
        self.assertEqual(methods["tracepixel-post-p7-v1"]["mean"]["readability_at_native_1x"], 3.642857142857143)
        self.assertEqual(methods["tracepixel-post-p7-v1"]["mean"]["style_coherence"], 3.857142857142857)

    def test_b1_owner_review_rejects_score_drift(self) -> None:
        payload = json.loads(OWNER.read_text(encoding="utf-8"))
        manifest, manifest_sha = load_review_manifest()
        bad = copy.deepcopy(payload)
        bad["ratings"][0]["recognizability"] = 6
        with self.assertRaises(ReviewContractError):
            validate_owner_review(bad, manifest, manifest_sha)


if __name__ == "__main__":
    unittest.main()
