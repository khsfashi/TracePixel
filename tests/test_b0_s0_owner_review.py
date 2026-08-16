from __future__ import annotations

import unittest

from evidence.b0_s0.review import (
    B0_FREEZE_COMMIT,
    DEFAULT_PREREGISTRATION,
    DEFAULT_RESULTS_ROOT,
    DEFAULT_REVIEW_ROOT,
    OWNER_REVIEW_SCHEMA_V1,
    ReviewApp,
    ReviewContractError,
    owner_review_summary,
    validate_owner_review,
)


class B0S0OwnerReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = ReviewApp(DEFAULT_PREREGISTRATION, DEFAULT_RESULTS_ROOT, DEFAULT_REVIEW_ROOT)

    def _ratings(self) -> list[dict[str, object]]:
        ratings: list[dict[str, object]] = []
        for raw_entry in self.app.review_manifest["entries"]:
            entry = dict(raw_entry)
            ratings.append(
                {
                    "review_id": entry["review_id"],
                    "task_id": entry["task_id"],
                    "trial_index": entry["trial_index"],
                    "order": entry["order"],
                    "recognizability": 3,
                    "readability_at_native_1x": 3,
                    "style_coherence": 3,
                    "human_rejection": False,
                }
            )
        return ratings

    def _payload(self) -> dict[str, object]:
        return {
            "schema": OWNER_REVIEW_SCHEMA_V1,
            "freeze_commit": B0_FREEZE_COMMIT,
            "review_manifest_sha256": self.app.manifest_sha,
            "evaluator_role": "repository owner",
            "dimensions": ["recognizability", "readability_at_native_1x", "style_coherence"],
            "ratings": self._ratings(),
        }

    def test_retained_package_is_complete_and_blind(self) -> None:
        self.assertEqual(len(self.app.manifests), 28)
        self.assertEqual(len(self.app.review_manifest["entries"]), 28)
        self.assertNotIn(b"tracepixel-staged-v1", self.app.page)
        self.assertNotIn(b"raw-pixel-program-v1", self.app.page)

    def test_valid_ratings_unblind_only_for_summary(self) -> None:
        ratings = validate_owner_review(self._payload(), self.app.review_manifest, self.app.manifest_sha)
        summary = owner_review_summary(ratings, self.app.by_review_id)
        methods = {item["method_id"]: item for item in summary["methods"]}
        self.assertEqual(set(methods), {"tracepixel-staged-v1", "raw-pixel-program-v1"})
        for item in methods.values():
            self.assertEqual(item["rated_artifacts"], 14)
            self.assertEqual(item["human_rejection_count"], 0)
            self.assertEqual(item["mean"], {"recognizability": 3.0, "readability_at_native_1x": 3.0, "style_coherence": 3.0})

    def test_method_label_leak_is_rejected_before_seal(self) -> None:
        payload = self._payload()
        ratings = payload["ratings"]
        ratings[0]["method_id"] = "tracepixel-staged-v1"
        with self.assertRaises(ReviewContractError):
            validate_owner_review(payload, self.app.review_manifest, self.app.manifest_sha)

    def test_missing_dimension_is_rejected(self) -> None:
        payload = self._payload()
        ratings = payload["ratings"]
        del ratings[0]["style_coherence"]
        with self.assertRaises(ReviewContractError):
            validate_owner_review(payload, self.app.review_manifest, self.app.manifest_sha)


if __name__ == "__main__":
    unittest.main()
