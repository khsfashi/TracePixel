from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tracepixel.model.asset_set_schedule_validation import asset_request_sha256
from tracepixel.model.simple_creature_request_validation import (
    SimpleCreatureRequestValidationError,
    simple_creature_evidence_policy_sha256,
    validate_simple_creature_request,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "evidence" / "p10_c1" / "simple-creature-profile.v1.json"
POSE = ROOT / "evidence" / "p10_c2" / "creature-pose.v1.json"
POLICY = ROOT / "evidence" / "p10_c3" / "simple-creature-evidence-policy.v1.json"
ASSET_REQUEST = ROOT / "evidence" / "p10_c3" / "asset-request.v1.json"
CREATURE_REQUEST = ROOT / "evidence" / "p10_c3" / "simple-creature-request.v1.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


class SimpleCreatureRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = _json(PROFILE)
        self.pose = _json(POSE)
        self.policy = _json(POLICY)
        self.asset_request = _json(ASSET_REQUEST)
        self.request = _json(CREATURE_REQUEST)

    def _validate(
        self,
        *,
        request: object | None = None,
        asset_request: object | None = None,
        profile: object | None = None,
        pose: object | None = None,
        policy: object | None = None,
    ) -> object:
        return validate_simple_creature_request(
            self.request if request is None else request,
            asset_request=self.asset_request if asset_request is None else asset_request,
            morphology_profile=self.profile if profile is None else profile,
            creature_pose=self.pose if pose is None else pose,
            evidence_policy=self.policy if policy is None else policy,
        )

    def test_retained_request_binds_existing_single_asset_path(self) -> None:
        self.assertIs(self.request, self._validate())
        self.assertEqual(self.request["request_sha256"], asset_request_sha256(self.asset_request))
        policy_ref = self.request["evidence_policy_ref"]
        assert type(policy_ref) is dict
        self.assertEqual(policy_ref["sha256"], simple_creature_evidence_policy_sha256(self.policy))

    def test_asset_request_payload_is_digest_bound(self) -> None:
        changed = deepcopy(self.asset_request)
        changed["instruction"] = "Create a different creature."
        with self.assertRaisesRegex(SimpleCreatureRequestValidationError, "asset_request_digest_mismatch"):
            self._validate(asset_request=changed)

    def test_asset_request_must_be_explicitly_simple_creature(self) -> None:
        changed = deepcopy(self.asset_request)
        art_intent = changed["art_intent"]
        assert type(art_intent) is dict
        art_intent["asset_class"] = "item-icon"
        with self.assertRaisesRegex(SimpleCreatureRequestValidationError, "invalid_asset_class"):
            self._validate(asset_request=changed)

    def test_asset_request_must_carry_exact_bound_morphology_profile(self) -> None:
        changed = deepcopy(self.asset_request)
        refs = changed["profile_refs"]
        assert type(refs) is list and type(refs[0]) is dict
        refs[0]["sha256"] = "0" * 64
        changed_request = deepcopy(self.request)
        changed_request["request_sha256"] = asset_request_sha256(changed)
        with self.assertRaisesRegex(SimpleCreatureRequestValidationError, "missing_bound_morphology_profile"):
            self._validate(request=changed_request, asset_request=changed)

    def test_morphology_reference_tampering_is_rejected(self) -> None:
        changed = deepcopy(self.request)
        morphology_ref = changed["morphology_ref"]
        assert type(morphology_ref) is dict
        morphology_ref["sha256"] = "0" * 64
        with self.assertRaisesRegex(SimpleCreatureRequestValidationError, "morphology_binding_mismatch"):
            self._validate(request=changed)

    def test_pose_reference_tampering_is_rejected(self) -> None:
        changed = deepcopy(self.request)
        pose_ref = changed["pose_ref"]
        assert type(pose_ref) is dict
        pose_ref["sha256"] = "0" * 64
        with self.assertRaisesRegex(SimpleCreatureRequestValidationError, "pose_binding_mismatch"):
            self._validate(request=changed)

    def test_perceptual_evidence_cannot_be_promoted_to_deterministic_truth(self) -> None:
        changed = deepcopy(self.policy)
        deterministic = changed["deterministic_facts"]
        assert type(deterministic) is list
        deterministic.append("species-or-form-recognizability")
        with self.assertRaisesRegex(SimpleCreatureRequestValidationError, "deterministic_evidence_drift"):
            self._validate(policy=changed)

        changed = deepcopy(self.policy)
        changed["vlm_is_deterministic_correctness"] = True
        with self.assertRaisesRegex(SimpleCreatureRequestValidationError, "vlm_authority_drift"):
            self._validate(policy=changed)

    def test_wrapper_is_closed_and_cannot_carry_pixels_or_solver_state(self) -> None:
        changed = deepcopy(self.request)
        changed["pixels"] = []
        with self.assertRaisesRegex(SimpleCreatureRequestValidationError, "invalid_fields"):
            self._validate(request=changed)


if __name__ == "__main__":
    unittest.main()
