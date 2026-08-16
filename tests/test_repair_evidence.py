from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tracepixel.qa import QA_POLICY_SCHEMA_V1, analyze_structural, evaluate_qa_policy
from tracepixel.raster import Canvas
from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    REPAIR_EVIDENCE_SCHEMA_V1,
    RepairEvidenceValidationError,
    build_repair_evidence,
    create_repair_plan,
    localize_feedback_intake,
    validate_repair_evidence,
    write_repair_evidence_bundle,
)


class _QaEvaluator:
    def evaluate(self, canvas: Canvas) -> dict[str, object]:
        policy = {
            "schema": QA_POLICY_SCHEMA_V1,
            "rules": [{"rule": "structural.no_edge_contact", "severity": "error"}],
        }
        return evaluate_qa_policy(policy, structural=analyze_structural(canvas))


def _plan() -> dict[str, object]:
    intake = {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "repair-evidence-asset",
            "task_id": "P7-F4-test",
            "canvas": {"width": 4, "height": 4},
            "artifact_sha256": None,
        },
        "items": [
            {
                "id": "edge-repair",
                "authority": "deterministic_qa",
                "source_ref": "test:qa",
                "summary": "Move occupancy away from the left edge.",
                "stage_hint": "silhouette",
                "region_hint": {"x": 0, "y": 1, "width": 2, "height": 1},
                "deterministic_qa": {
                    "rule": "structural.no_edge_contact",
                    "category": "structural",
                    "severity": "error",
                },
                "human": None,
            },
            {
                "id": "owner-defer",
                "authority": "owner_human",
                "source_ref": "test:owner",
                "summary": "Owner perception has no explicit repair pixels.",
                "stage_hint": None,
                "region_hint": None,
                "deterministic_qa": None,
                "human": {
                    "human_rejection": True,
                    "scores": [{"dimension": "style_coherence", "value": 2}],
                },
            },
        ],
    }
    localization = localize_feedback_intake(intake)
    return create_repair_plan(
        localization,
        [
            {
                "feedback_id": "edge-repair",
                "target_stage": "silhouette",
                "program": {
                    "schema": "tracepixel.pixel-program.v1",
                    "canvas": {"width": 4, "height": 4},
                    "operations": [
                        {
                            "op": "set_pixels",
                            "pixels": [
                                [0, 1, 0, 0, 0, 0],
                                [1, 1, 255, 0, 0, 255],
                            ],
                        }
                    ],
                },
                "defer_reason": None,
            },
            {
                "feedback_id": "owner-defer",
                "target_stage": None,
                "program": None,
                "defer_reason": "No explicit owner repair pixels are available.",
            },
        ],
    )


def _canvas() -> Canvas:
    canvas = Canvas(4, 4)
    canvas.set_pixels(
        [
            (0, 1, (255, 0, 0, 255)),
            (1, 1, (255, 0, 0, 255)),
        ]
    )
    return canvas


class RepairEvidenceTests(unittest.TestCase):
    def test_build_binds_before_after_png_and_exact_qa_to_f3_execution(self) -> None:
        canvas = _canvas()
        bundle = build_repair_evidence(
            _plan(),
            canvas=canvas,
            qa_evaluator=_QaEvaluator(),
            preview_scale=8,
        )
        manifest = validate_repair_evidence(bundle.manifest)

        self.assertEqual(manifest["schema"], REPAIR_EVIDENCE_SCHEMA_V1)
        execution = manifest["execution"]
        self.assertNotEqual(execution["source_rgba_sha256"], execution["result_rgba_sha256"])
        self.assertEqual(execution["observed_changed_pixel_count"], 1)
        self.assertTrue(execution["unaffected_region_stable"])
        self.assertEqual(execution["qa"]["findings"], [])

        self.assertEqual(
            manifest["before_native_png"]["authoritative_rgba_sha256"],
            execution["source_rgba_sha256"],
        )
        self.assertEqual(
            manifest["before_preview_png"]["authoritative_rgba_sha256"],
            execution["source_rgba_sha256"],
        )
        self.assertEqual(
            manifest["after_native_png"]["authoritative_rgba_sha256"],
            execution["result_rgba_sha256"],
        )
        self.assertEqual(
            manifest["after_preview_png"]["authoritative_rgba_sha256"],
            execution["result_rgba_sha256"],
        )

        for key in (
            "before_native_png",
            "before_preview_png",
            "after_native_png",
            "after_preview_png",
        ):
            self.assertTrue(bundle.file_bytes(manifest[key]["path"]).startswith(b"\x89PNG\r\n\x1a\n"))

        expected_qa = json.dumps(
            execution["qa"],
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(bundle.file_bytes("evidence/qa-findings.json"), expected_qa)

    def test_static_gallery_is_offline_scriptless_mobile_safe_and_authority_bounded(self) -> None:
        bundle = build_repair_evidence(
            _plan(),
            canvas=_canvas(),
            qa_evaluator=_QaEvaluator(),
        )
        gallery = bundle.file_bytes("index.html").decode("utf-8")
        lowered = gallery.lower()

        self.assertNotIn("<script", lowered)
        self.assertNotIn("http://", lowered)
        self.assertNotIn("https://", lowered)
        self.assertIn("content-security-policy", lowered)
        self.assertIn("data:image/png;base64,", lowered)
        self.assertIn("overflow-wrap:anywhere", lowered)
        self.assertIn("grid-template-columns:1fr", lowered)
        self.assertIn("Human feedback remains P7-F5", gallery)
        self.assertEqual(bundle.manifest["authority"]["human"], "not-recorded")
        self.assertEqual(bundle.manifest["authority"]["perceptual"], "not-included")

    def test_repeated_build_is_byte_deterministic_for_same_inputs(self) -> None:
        first = build_repair_evidence(
            _plan(),
            canvas=_canvas(),
            qa_evaluator=_QaEvaluator(),
        )
        second = build_repair_evidence(
            _plan(),
            canvas=_canvas(),
            qa_evaluator=_QaEvaluator(),
        )

        self.assertEqual(first.manifest, second.manifest)
        self.assertEqual(
            [(item.path, item.data) for item in first.files],
            [(item.path, item.data) for item in second.files],
        )

    def test_validator_rejects_forged_before_raster_identity(self) -> None:
        bundle = build_repair_evidence(
            _plan(),
            canvas=_canvas(),
            qa_evaluator=_QaEvaluator(),
        )
        forged = copy.deepcopy(bundle.manifest)
        forged["before_native_png"]["authoritative_rgba_sha256"] = forged["execution"][
            "result_rgba_sha256"
        ]

        with self.assertRaises(RepairEvidenceValidationError) as raised:
            validate_repair_evidence(forged)
        self.assertEqual(raised.exception.code, "artifact_raster_identity_mismatch")
        self.assertEqual(
            raised.exception.path,
            "$.before_native_png.authoritative_rgba_sha256",
        )

    def test_validator_rejects_human_or_perceptual_authority_promotion(self) -> None:
        bundle = build_repair_evidence(
            _plan(),
            canvas=_canvas(),
            qa_evaluator=_QaEvaluator(),
        )
        forged = copy.deepcopy(bundle.manifest)
        forged["authority"]["human"] = "approved"

        with self.assertRaises(RepairEvidenceValidationError) as raised:
            validate_repair_evidence(forged)
        self.assertEqual(raised.exception.code, "invalid_authority_boundary")

    def test_preview_scale_must_be_exact_integer_at_least_two(self) -> None:
        for scale in (1, True, 1.5):
            with self.subTest(scale=scale):
                with self.assertRaises(RepairEvidenceValidationError) as raised:
                    build_repair_evidence(
                        _plan(),
                        canvas=_canvas(),
                        qa_evaluator=_QaEvaluator(),
                        preview_scale=scale,  # type: ignore[arg-type]
                    )
                self.assertEqual(raised.exception.code, "invalid_preview_scale")

    def test_writer_materializes_complete_bundle_and_refuses_stale_directory(self) -> None:
        bundle = build_repair_evidence(
            _plan(),
            canvas=_canvas(),
            qa_evaluator=_QaEvaluator(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "evidence"
            write_repair_evidence_bundle(bundle, output)
            for item in bundle.files:
                self.assertEqual(output.joinpath(*item.path.split("/")).read_bytes(), item.data)

            stale = root / "stale"
            stale.mkdir()
            (stale / "old.txt").write_text("stale", encoding="utf-8")
            with self.assertRaises(RepairEvidenceValidationError) as raised:
                write_repair_evidence_bundle(bundle, stale)
            self.assertEqual(raised.exception.code, "output_not_empty")


if __name__ == "__main__":
    unittest.main()
