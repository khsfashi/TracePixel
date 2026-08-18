from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tracepixel.model.humanoid_pose import HUMANOID_POSE_SCHEMA_V1
from tracepixel.model.humanoid_pose_validation import (
    HumanoidPoseValidationError,
    humanoid_pose_sha256,
    validate_humanoid_pose,
    validate_humanoid_pose_reference,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE_FIXTURE = ROOT / "evidence" / "g8_h1" / "humanoid-profile.v1.json"
POSE_FIXTURE = ROOT / "evidence" / "g8_h2" / "humanoid-pose.v1.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


def _profile() -> dict[str, object]:
    return _json(PROFILE_FIXTURE)


def _pose() -> dict[str, object]:
    return _json(POSE_FIXTURE)


class HumanoidPoseTests(unittest.TestCase):
    def test_retained_humanoid_pose_validates(self) -> None:
        profile = _profile()
        pose = _pose()
        self.assertIs(pose, validate_humanoid_pose(pose, profile))
        self.assertEqual(HUMANOID_POSE_SCHEMA_V1, pose["schema"])

    def test_pose_digest_covers_constraint_changes(self) -> None:
        profile = _profile()
        pose = _pose()
        digest = humanoid_pose_sha256(pose, profile)
        ref = {
            "pose_id": pose["pose_id"],
            "pose_schema": HUMANOID_POSE_SCHEMA_V1,
            "sha256": digest,
        }
        self.assertIs(ref, validate_humanoid_pose_reference(ref, pose, profile))

        changed = deepcopy(pose)
        relations = changed["relations"]
        assert type(relations) is list and type(relations[1]) is dict
        value_range = relations[1]["value_range"]
        assert type(value_range) is dict
        value_range["maximum"] = 25.0
        self.assertNotEqual(digest, humanoid_pose_sha256(changed, profile))
        with self.assertRaisesRegex(HumanoidPoseValidationError, "pose_digest_mismatch"):
            validate_humanoid_pose_reference(ref, changed, profile)

    def test_profile_digest_binding_fails_closed(self) -> None:
        profile = _profile()
        pose = _pose()
        profile_ref = pose["profile_ref"]
        assert type(profile_ref) is dict
        profile_ref["sha256"] = "0" * 64
        with self.assertRaisesRegex(HumanoidPoseValidationError, "profile_binding_mismatch"):
            validate_humanoid_pose(pose, profile)

    def test_unknown_pose_landmark_fails_closed(self) -> None:
        profile = _profile()
        pose = _pose()
        relations = pose["relations"]
        assert type(relations) is list and type(relations[0]) is dict
        relations[0]["landmark_ids"] = ["missing-landmark"]
        with self.assertRaisesRegex(HumanoidPoseValidationError, "unknown_landmark_reference"):
            validate_humanoid_pose(pose, profile)

    def test_articulation_requires_finite_degree_range(self) -> None:
        for minimum, maximum, unit in ((float("nan"), 20.0, "degrees"), (-15.0, 20.0, "pixels")):
            profile = _profile()
            pose = _pose()
            relations = pose["relations"]
            assert type(relations) is list and type(relations[1]) is dict
            value_range = relations[1]["value_range"]
            assert type(value_range) is dict
            value_range["minimum"] = minimum
            value_range["maximum"] = maximum
            value_range["unit"] = unit
            with self.assertRaises(HumanoidPoseValidationError):
                validate_humanoid_pose(pose, profile)

    def test_support_contact_must_use_profile_support_landmarks(self) -> None:
        profile = _profile()
        pose = _pose()
        relations = pose["relations"]
        assert type(relations) is list
        support = next(item for item in relations if type(item) is dict and item.get("kind") == "support-contact")
        assert type(support) is dict
        support["landmark_ids"] = ["hand-left"]
        with self.assertRaisesRegex(HumanoidPoseValidationError, "non_support_contact"):
            validate_humanoid_pose(pose, profile)

    def test_required_relation_kinds_must_all_exist(self) -> None:
        profile = _profile()
        pose = _pose()
        relations = pose["relations"]
        assert type(relations) is list
        pose["relations"] = [
            item for item in relations
            if not (type(item) is dict and item.get("kind") == "balance-contact")
        ]
        with self.assertRaisesRegex(HumanoidPoseValidationError, "missing_required_relation"):
            validate_humanoid_pose(pose, profile)

    def test_equipment_anchor_reference_and_side_must_match_profile(self) -> None:
        profile = _profile()
        pose = _pose()
        attachments = pose["equipment_attachments"]
        assert type(attachments) is list and type(attachments[0]) is dict
        attachments[0]["side_intent"] = "left"
        with self.assertRaisesRegex(HumanoidPoseValidationError, "anchor_side_mismatch"):
            validate_humanoid_pose(pose, profile)

        pose = _pose()
        attachments = pose["equipment_attachments"]
        assert type(attachments) is list and type(attachments[0]) is dict
        attachments[0]["anchor_id"] = "missing-anchor"
        with self.assertRaisesRegex(HumanoidPoseValidationError, "unknown_equipment_anchor"):
            validate_humanoid_pose(pose, profile)

    def test_clear_anchor_cannot_claim_equipment_or_occlusion(self) -> None:
        profile = _profile()
        pose = _pose()
        attachments = pose["equipment_attachments"]
        assert type(attachments) is list and type(attachments[1]) is dict
        attachments[1]["equipment_id"] = "unexpected-item"
        with self.assertRaisesRegex(HumanoidPoseValidationError, "clear_anchor_has_equipment"):
            validate_humanoid_pose(pose, profile)

        pose = _pose()
        attachments = pose["equipment_attachments"]
        assert type(attachments) is list and type(attachments[1]) is dict
        attachments[1]["overlap_occlusion_intent"] = "behind"
        with self.assertRaisesRegex(HumanoidPoseValidationError, "clear_anchor_has_occlusion"):
            validate_humanoid_pose(pose, profile)

    def test_anchor_occupancy_is_single_writer(self) -> None:
        profile = _profile()
        pose = _pose()
        attachments = pose["equipment_attachments"]
        assert type(attachments) is list and type(attachments[0]) is dict and type(attachments[1]) is dict
        attachments[1]["anchor_id"] = attachments[0]["anchor_id"]
        attachments[1]["side_intent"] = attachments[0]["side_intent"]
        with self.assertRaisesRegex(HumanoidPoseValidationError, "duplicate_anchor_occupancy"):
            validate_humanoid_pose(pose, profile)


if __name__ == "__main__":
    unittest.main()
