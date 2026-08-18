from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tracepixel.model.humanoid_profile import HUMANOID_PROFILE_SCHEMA_V1
from tracepixel.model.humanoid_profile_validation import (
    HumanoidProfileValidationError,
    humanoid_profile_sha256,
    validate_humanoid_profile,
    validate_humanoid_profile_reference,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evidence" / "g8_h1" / "humanoid-profile.v1.json"


def _profile() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


class HumanoidProfileTests(unittest.TestCase):
    def test_retained_humanoid_profile_validates(self) -> None:
        profile = _profile()
        self.assertIs(profile, validate_humanoid_profile(profile))
        self.assertEqual(HUMANOID_PROFILE_SCHEMA_V1, profile["schema"])

    def test_profile_digest_covers_structural_changes(self) -> None:
        profile = _profile()
        digest = humanoid_profile_sha256(profile)
        ref = {
            "profile_id": profile["profile_id"],
            "profile_schema": HUMANOID_PROFILE_SCHEMA_V1,
            "sha256": digest,
        }
        self.assertIs(ref, validate_humanoid_profile_reference(ref, profile))

        changed = deepcopy(profile)
        proportions = changed["proportion_constraints"]
        assert type(proportions) is list and type(proportions[0]) is dict
        ratio = proportions[0]["ratio_range"]
        assert type(ratio) is dict
        ratio["maximum"] = 0.4
        self.assertNotEqual(digest, humanoid_profile_sha256(changed))
        with self.assertRaisesRegex(HumanoidProfileValidationError, "profile_digest_mismatch"):
            validate_humanoid_profile_reference(ref, changed)

    def test_unknown_landmark_reference_fails_closed(self) -> None:
        profile = _profile()
        proportions = profile["proportion_constraints"]
        assert type(proportions) is list and type(proportions[0]) is dict
        proportions[0]["landmark_ids"] = ["head", "missing-landmark"]
        with self.assertRaisesRegex(HumanoidProfileValidationError, "unknown_landmark_reference"):
            validate_humanoid_profile(profile)

    def test_mirror_relations_must_be_reciprocal(self) -> None:
        profile = _profile()
        landmarks = profile["landmarks"]
        assert type(landmarks) is list
        right_hand = next(item for item in landmarks if type(item) is dict and item.get("landmark_id") == "hand-right")
        assert type(right_hand) is dict
        right_hand["mirror_landmark_id"] = None
        with self.assertRaisesRegex(HumanoidProfileValidationError, "nonreciprocal_mirror|missing_mirror_landmark"):
            validate_humanoid_profile(profile)

    def test_required_ratio_range_must_be_finite_and_ordered(self) -> None:
        for minimum, maximum in ((float("nan"), 0.3), (0.5, 0.3)):
            profile = _profile()
            proportions = profile["proportion_constraints"]
            assert type(proportions) is list and type(proportions[0]) is dict
            ratio = proportions[0]["ratio_range"]
            assert type(ratio) is dict
            ratio["minimum"] = minimum
            ratio["maximum"] = maximum
            with self.assertRaises(HumanoidProfileValidationError):
                validate_humanoid_profile(profile)

    def test_identity_feature_kinds_are_both_required(self) -> None:
        profile = _profile()
        features = profile["identity_features"]
        assert type(features) is list
        profile["identity_features"] = [
            item for item in features
            if not (type(item) is dict and item.get("kind") == "silhouette-critical")
        ]
        with self.assertRaisesRegex(HumanoidProfileValidationError, "missing_identity_feature_kind"):
            validate_humanoid_profile(profile)

    def test_equipment_anchor_side_must_match_landmark(self) -> None:
        profile = _profile()
        anchors = profile["equipment_anchors"]
        assert type(anchors) is list and type(anchors[0]) is dict
        anchors[0]["side"] = "right"
        with self.assertRaisesRegex(HumanoidProfileValidationError, "anchor_side_mismatch"):
            validate_humanoid_profile(profile)

    def test_unknown_category_requires_declared_unknown(self) -> None:
        profile = _profile()
        declarations = profile["category_declarations"]
        assert type(declarations) is list and type(declarations[0]) is dict
        declarations[0]["status"] = "unknown"
        declarations[0]["unknown_id"] = "not-declared"
        with self.assertRaisesRegex(HumanoidProfileValidationError, "unknown_unknown_reference"):
            validate_humanoid_profile(profile)


if __name__ == "__main__":
    unittest.main()
