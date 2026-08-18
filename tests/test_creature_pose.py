from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tracepixel.model.creature_pose import CREATURE_POSE_SCHEMA_V1
from tracepixel.model.creature_pose_validation import (
    CreaturePoseValidationError,
    creature_pose_sha256,
    validate_creature_pose,
    validate_creature_pose_reference,
)
from tracepixel.model.research_profile_validation import morphology_profile_sha256

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "evidence" / "p10_c1" / "simple-creature-profile.v1.json"


def _profile() -> dict[str, object]:
    value = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


def _pose(profile: dict[str, object]) -> dict[str, object]:
    return {
        "schema": CREATURE_POSE_SCHEMA_V1,
        "pose_id": "fixture-grounded-alert",
        "pose_name": "Grounded three-quarter alert",
        "morphology_ref": {
            "profile_id": profile["profile_id"],
            "profile_schema": "tracepixel.morphology-profile.v1",
            "sha256": morphology_profile_sha256(profile),
        },
        "orientation_intent": {
            "facing": "three-quarter-right",
            "description": "Read as a grounded alert pose without implying camera projection, IK, or raster coordinates.",
        },
        "relations": [
            {
                "relation_id": "coarse-head-trunk-read",
                "kind": "landmark-relation",
                "mode": "hint",
                "landmark_ids": ["head", "trunk"],
                "value_range": None,
                "morphology_constraint_ids": ["head-ratio"],
                "text": "Keep the head-to-trunk grouping readable.",
            },
            {
                "relation_id": "alert-head-angle",
                "kind": "articulation",
                "mode": "required-range",
                "landmark_ids": ["head", "trunk"],
                "value_range": {"minimum": -20.0, "maximum": 25.0, "unit": "degrees"},
                "morphology_constraint_ids": ["head-joint"],
                "text": "Keep the alert head articulation inside the narrower pose range.",
            },
            {
                "relation_id": "grounded-supports",
                "kind": "support-contact",
                "mode": "hint",
                "landmark_ids": ["support-left", "support-right"],
                "value_range": None,
                "morphology_constraint_ids": ["support-contact"],
                "text": "Retain both declared support contacts without performing a physics solve.",
            },
            {
                "relation_id": "facing-head-silhouette",
                "kind": "silhouette-facing",
                "mode": "hint",
                "landmark_ids": ["head", "trunk"],
                "value_range": None,
                "morphology_constraint_ids": ["head-silhouette"],
                "text": "Preserve the head break that supports the declared facing intent.",
            },
        ],
    }


class CreaturePoseTests(unittest.TestCase):
    def test_pose_validates_against_exact_morphology_digest(self) -> None:
        profile = _profile()
        pose = _pose(profile)
        self.assertIs(pose, validate_creature_pose(pose, profile))

    def test_morphology_digest_binding_fails_closed(self) -> None:
        profile = _profile()
        pose = _pose(profile)
        morphology_ref = pose["morphology_ref"]
        assert type(morphology_ref) is dict
        morphology_ref["sha256"] = "0" * 64
        with self.assertRaisesRegex(CreaturePoseValidationError, "morphology_binding_mismatch"):
            validate_creature_pose(pose, profile)

    def test_unknown_or_uncovered_landmarks_fail_closed(self) -> None:
        profile = _profile()
        pose = _pose(profile)
        relations = pose["relations"]
        assert type(relations) is list and type(relations[2]) is dict
        relations[2]["landmark_ids"] = ["head"]
        with self.assertRaisesRegex(CreaturePoseValidationError, "uncovered_pose_landmark"):
            validate_creature_pose(pose, profile)

        pose = _pose(profile)
        relations = pose["relations"]
        assert type(relations) is list and type(relations[0]) is dict
        relations[0]["landmark_ids"] = ["missing-landmark"]
        with self.assertRaisesRegex(CreaturePoseValidationError, "unknown_landmark_reference"):
            validate_creature_pose(pose, profile)

    def test_articulation_range_must_be_finite_and_inside_morphology(self) -> None:
        profile = _profile()
        for minimum, maximum, expected in (
            (float("nan"), 10.0, "invalid_value"),
            (-60.0, 25.0, "articulation_outside_morphology"),
        ):
            pose = _pose(profile)
            relations = pose["relations"]
            assert type(relations) is list and type(relations[1]) is dict
            value_range = relations[1]["value_range"]
            assert type(value_range) is dict
            value_range["minimum"] = minimum
            value_range["maximum"] = maximum
            with self.assertRaisesRegex(CreaturePoseValidationError, expected):
                validate_creature_pose(pose, profile)

    def test_stylization_tolerance_is_available_but_bounded_by_morphology(self) -> None:
        profile = _profile()
        pose = _pose(profile)
        relations = pose["relations"]
        assert type(relations) is list
        relations.append(
            {
                "relation_id": "pose-pixel-tolerance",
                "kind": "landmark-relation",
                "mode": "stylization-tolerance",
                "landmark_ids": ["head", "support-left", "support-right"],
                "value_range": {"minimum": 0.0, "maximum": 1.5, "unit": "pixels"},
                "morphology_constraint_ids": ["pixel-tolerance"],
                "text": "Allow a narrower pose-specific low-resolution exaggeration tolerance.",
            }
        )
        self.assertIs(pose, validate_creature_pose(pose, profile))
        tolerance = relations[-1]
        assert type(tolerance) is dict and type(tolerance["value_range"]) is dict
        tolerance["value_range"]["maximum"] = 3.0
        with self.assertRaisesRegex(CreaturePoseValidationError, "relation_range_outside_morphology"):
            validate_creature_pose(pose, profile)

    def test_required_pose_capabilities_cannot_disappear(self) -> None:
        profile = _profile()
        pose = _pose(profile)
        relations = pose["relations"]
        assert type(relations) is list
        pose["relations"] = [
            item for item in relations
            if not (type(item) is dict and item.get("kind") == "silhouette-facing")
        ]
        with self.assertRaisesRegex(CreaturePoseValidationError, "missing_required_relation"):
            validate_creature_pose(pose, profile)

    def test_pose_digest_and_reference_detect_drift(self) -> None:
        profile = _profile()
        pose = _pose(profile)
        digest = creature_pose_sha256(pose, profile)
        ref = {
            "pose_id": pose["pose_id"],
            "pose_schema": CREATURE_POSE_SCHEMA_V1,
            "sha256": digest,
        }
        self.assertIs(ref, validate_creature_pose_reference(ref, pose, profile))

        changed = deepcopy(pose)
        orientation = changed["orientation_intent"]
        assert type(orientation) is dict
        orientation["facing"] = "left"
        self.assertNotEqual(digest, creature_pose_sha256(changed, profile))
        with self.assertRaisesRegex(CreaturePoseValidationError, "pose_digest_mismatch"):
            validate_creature_pose_reference(ref, changed, profile)


if __name__ == "__main__":
    unittest.main()
