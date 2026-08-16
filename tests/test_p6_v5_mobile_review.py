from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evidence.p6_v3.checkpoint import build_reference_gallery
from evidence.p6_v5.checkpoint import (
    ARTIFACT_PREFIX,
    MOBILE_REVIEW_PROOF_SCHEMA_V2,
    MobileReviewContractError,
    validate_mobile_review_package,
    validate_mobile_review_proof,
    validate_mobile_review_surface,
)
from tracepixel.preview.mobile_review import (
    build_mobile_review_package,
    write_mobile_review_package,
)


SOURCE_SHA = "8b9663596105986baf0d5c6daa3da2bd8ea313a9"


def _proof() -> dict[str, object]:
    return {
        "schema": MOBILE_REVIEW_PROOF_SCHEMA_V2,
        "repository": "khsfashi/TracePixel",
        "source_sha": SOURCE_SHA,
        "workflow_run_id": 31926276771,
        "artifact_id": 9257921456,
        "artifact_name": ARTIFACT_PREFIX + SOURCE_SHA,
        "language": "ko",
        "review_page": "index.ko.html",
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
    def _package(self):
        return build_mobile_review_package(build_reference_gallery())

    def test_bilingual_reference_package_exposes_all_phone_review_targets(self) -> None:
        package = self._package()
        validate_mobile_review_package(package)
        self.assertEqual(package.manifest["stage_linkage"], "separate-reference")
        self.assertIn(b'href="index.ko.html"', package.html_en)
        self.assertIn(b'href="index.html"', package.html_ko)
        self.assertIn("이 최종 결과의 실제 생성 이력이 아닙니다".encode(), package.html_ko)

    def test_missing_review_section_is_rejected(self) -> None:
        package = self._package()
        document = package.html_en.replace(
            b'id="stages-title"',
            b'id="removed-stages-title"',
            1,
        )
        with self.assertRaises(MobileReviewContractError):
            validate_mobile_review_surface(
                document,
                language="en",
                expected_stage_linkage="separate-reference",
            )

    def test_reordered_review_sections_are_rejected(self) -> None:
        package = self._package()
        document = package.html_en
        document = document.replace(b'id="final-title"', b'id="swap-title"', 1)
        document = document.replace(b'id="qa-title"', b'id="final-title"', 1)
        document = document.replace(b'id="swap-title"', b'id="qa-title"', 1)
        with self.assertRaises(MobileReviewContractError):
            validate_mobile_review_surface(
                document,
                language="en",
                expected_stage_linkage="separate-reference",
            )

    def test_static_language_navigation_is_required(self) -> None:
        package = self._package()
        document = package.html_ko.replace(b'href="index.html"', b'href="missing.html"', 1)
        with self.assertRaises(MobileReviewContractError):
            validate_mobile_review_surface(
                document,
                language="ko",
                expected_stage_linkage="separate-reference",
            )

    def test_writer_materializes_exact_bilingual_payload(self) -> None:
        package = self._package()
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "review"
            write_mobile_review_package(package, output)
            self.assertEqual((output / "index.html").read_bytes(), package.html_en)
            self.assertEqual((output / "index.ko.html").read_bytes(), package.html_ko)
            self.assertEqual(
                json.loads((output / "manifest.json").read_text(encoding="utf-8")),
                package.manifest,
            )

    def test_valid_owner_phone_proof_is_accepted(self) -> None:
        validate_mobile_review_proof(_proof())

    def test_proof_language_must_match_review_page(self) -> None:
        proof = _proof()
        proof["review_page"] = "index.html"
        with self.assertRaises(MobileReviewContractError):
            validate_mobile_review_proof(proof)

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
