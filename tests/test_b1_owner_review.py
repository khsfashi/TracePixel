from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evidence.b1_s0.review import (
    ReviewContractError,
    load_review_manifest,
    owner_review_summary,
    validate_owner_review,
)

FREEZE = "ca612a026ff5e74c397d9aa4ef8c0bdb25d1df6a"
OWNER = Path("evidence/b1/review") / FREEZE / "owner-review.json"
SUMMARY = Path("evidence/b1/review") / FREEZE / "owner-review-summary.json"


def test_b1_owner_review_is_bound_to_frozen_blind_manifest() -> None:
    payload = json.loads(OWNER.read_text(encoding="utf-8"))
    manifest, manifest_sha = load_review_manifest()

    assert manifest_sha == "d51aa6a4ad264ef52a473c74810c416c98caefe466ab19eca2a0d60792dfe419"
    ratings, mapping = validate_owner_review(payload, manifest, manifest_sha)
    assert len(ratings) == 28
    assert len(mapping) == 28

    summary = owner_review_summary(ratings, mapping)
    assert summary == json.loads(SUMMARY.read_text(encoding="utf-8"))
    methods = {item["method_id"]: item for item in summary["methods"]}
    assert methods["raw-pixel-program-v1"]["human_rejection_count"] == 1
    assert methods["raw-pixel-program-v1"]["mean"] == {
        "recognizability": 4.0,
        "readability_at_native_1x": 4.0,
        "style_coherence": 3.9285714285714284,
    }
    assert methods["tracepixel-post-p7-v1"]["human_rejection_count"] == 0
    assert methods["tracepixel-post-p7-v1"]["mean"] == {
        "recognizability": 4.0,
        "readability_at_native_1x": 3.642857142857143,
        "style_coherence": 3.857142857142857,
    }


def test_b1_owner_review_rejects_score_drift() -> None:
    payload = json.loads(OWNER.read_text(encoding="utf-8"))
    manifest, manifest_sha = load_review_manifest()
    bad = copy.deepcopy(payload)
    bad["ratings"][0]["recognizability"] = 6

    with pytest.raises(ReviewContractError, match="integer 1-5"):
        validate_owner_review(bad, manifest, manifest_sha)
