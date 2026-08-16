from __future__ import annotations

import unittest

from evidence.p6_v3.checkpoint import build_reference_gallery
from evidence.p6_v5.checkpoint import (
    ARTIFACT_PREFIX,
    MOBILE_REVIEW_PROOF_SCHEMA_V1,
    MobileReviewContractError,
    validate_mobile_review_proof,
    validate_mobile_review_surface,
)


SOURCE_SHA = "de4ca0a14cd1dbf80b45f9a34a562102f61b75e7"


def _proof() -> dict[str, object]:
    return {
        "schema": MOBILE_REVIEW_PROOF_SCHEMA_V1,
        "repository": "khsfashi/TracePixel",
        "source_sha": SOURCE_SHA,
        "workflow_run_id": 31925839319,
        "artifact_id": 9257790332,
        "artifact_name": ARTIFACT_PREFIX + SOURCE_SHA,
        "device_class": "phone",
        "access_path": "github-actions-artifact-download",
        "observations": {
            "task_intent": True,
            "final_output": True,
            "stage_progression": True,
            "deterministic_qa": True,
            "agent_complexity": True,
        },
        "perceptual_vlm_used": False,
        "self_hosted_runner_used": False,
    }


class P6V5MobileReviewTests(unittest.TestCase):
    def test_reference_gallery_exposes_all_phone_review_targets(self) -> None:
        validate_mobile_review_surface(build_reference_gallery().html)

    def test_missing_review_section_is_rejected(self) -> None:
        document = build_reference_gallery().html.replace(
            b'id="stages-title"',
            b'id="removed-stages-title"',
            1,
        )
        with self.assertRaises(MobileReviewContractError):
            validate_mobile_review_surface(document)

    def test_reordered_review_sections_are_rejected(self) -> None:
        document = build_reference_gallery().html
        document = document.replace(b'id="final-title"', b'id="swap-title"', 1)
        document = document.replace(b'id="qa-title"', b'id="final-title"', 1)
        document = document.replace(b'id="swap-title"', b'id="qa-title"', 1)
        with self.assertRaises(MobileReviewContractError):
            validate_mobile_review_surface(document)

    def test_valid_owner_phone_proof_is_accepted(self) -> None:
        validate_mobile_review_proof(_proof())

    def test_non_phone_proof_is_rejected(self) -> None:
        proof = _proof()
        proof["device_class"] = "desktop"
        with self.assertRaises(MobileReviewContractError):
            validate_mobile_review_proof(proof)

    def test_artifact_name_must_match_source_sha(self) -> None:
        proof = _proof()
        proof["artifact_name"] = ARTIFACT_PREFIX + ("0" * 40)
        with self.assertRaises(MobileReviewContractError):
            validate_mobile_review_proof(proof)

    def test_every_required_observation_must_be_positive(self) -> None:
        proof = _proof()
        observations = proof["observations"]
        assert isinstance(observations, dict)
        observations["agent_complexity"] = False
        with self.assertRaises(MobileReviewContractError):
            validate_mobile_review_proof(proof)

    def test_g4_or_g6_crossing_is_rejected(self) -> None:
        for key in ("perceptual_vlm_used", "self_hosted_runner_used"):
            proof = _proof()
            proof[key] = True
            with self.subTest(key=key), self.assertRaises(MobileReviewContractError):
                validate_mobile_review_proof(proof)


if __name__ == "__main__":
    unittest.main()
