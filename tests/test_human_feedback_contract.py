from __future__ import annotations

import copy
import unittest

from tracepixel.qa import QA_POLICY_SCHEMA_V1, analyze_structural, evaluate_qa_policy
from tracepixel.raster import Canvas
from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    HUMAN_FEEDBACK_SCHEMA_V1,
    HumanFeedbackValidationError,
    build_repair_evidence,
    create_human_feedback,
    create_repair_plan,
    localize_feedback_intake,
    validate_human_feedback,
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
            "asset_id": "human-feedback-asset",
            "task_id": "P7-F5-test",
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
            }
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
            }
        ],
    )


def _evidence() -> dict[str, object]:
    canvas = Canvas(4, 4)
    canvas.set_pixels(
        [
            (0, 1, (255, 0, 0, 255)),
            (1, 1, (255, 0, 0, 255)),
        ]
    )
    return build_repair_evidence(
        _plan(),
        canvas=canvas,
        qa_evaluator=_QaEvaluator(),
        preview_scale=8,
    ).manifest


def _owner_feedback(evidence: dict[str, object]) -> dict[str, object]:
    execution = evidence["execution"]
    target = execution["plan"]["localization"]["intake"]["target"]
    return {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": target["asset_id"],
            "task_id": target["task_id"],
            "canvas": copy.deepcopy(target["canvas"]),
            "artifact_sha256": evidence["after_native_png"]["sha256"],
        },
        "items": [
            {
                "id": "owner-style-repair",
                "authority": "owner_human",
                "source_ref": "test:owner-review",
                "summary": "The repaired output is structurally valid but still needs a clearer semantic detail.",
                "stage_hint": "semantic_details",
                "region_hint": {"x": 1, "y": 1, "width": 2, "height": 2},
                "deterministic_qa": None,
                "human": {
                    "human_rejection": True,
                    "scores": [{"dimension": "style_coherence", "value": 2}],
                },
            }
        ],
    }


class HumanFeedbackContractTests(unittest.TestCase):
    def test_accept_binds_exact_f4_manifest_without_defining_composite_completion(self) -> None:
        evidence = _evidence()
        review = create_human_feedback(
            evidence,
            source_ref="test:owner",
            decision="accept",
            summary="Owner accepts the reviewed result.",
        )
        validated = validate_human_feedback(review)

        self.assertEqual(validated["schema"], HUMAN_FEEDBACK_SCHEMA_V1)
        self.assertEqual(validated["evidence"], evidence)
        self.assertIsNone(validated["feedback_intake"])
        self.assertEqual(validated["completion"]["deterministic_qa_status"], "no-findings")
        self.assertEqual(validated["completion"]["human_authoring_status"], "accepted")
        self.assertEqual(validated["completion"]["composite_completion"], "not-defined")
        self.assertEqual(validated["authority"]["human"], "repository-owner")
        self.assertEqual(validated["authority"]["vlm"], "not-used")

    def test_request_repair_is_valid_even_when_deterministic_qa_has_no_findings(self) -> None:
        evidence = _evidence()
        feedback = _owner_feedback(evidence)
        review = create_human_feedback(
            evidence,
            source_ref="test:owner",
            decision="request_repair",
            summary="Structural QA is clear, but the owner requests another bounded repair.",
            feedback_intake=feedback,
        )

        self.assertEqual(review["completion"]["deterministic_qa_status"], "no-findings")
        self.assertEqual(review["completion"]["human_authoring_status"], "repair-requested")
        self.assertEqual(review["completion"]["composite_completion"], "not-defined")
        self.assertEqual(review["feedback_intake"], feedback)
        self.assertEqual(
            review["feedback_intake"]["target"]["artifact_sha256"],
            evidence["after_native_png"]["sha256"],
        )

    def test_accept_rejects_simultaneous_feedback_loop(self) -> None:
        evidence = _evidence()
        with self.assertRaises(HumanFeedbackValidationError) as raised:
            create_human_feedback(
                evidence,
                source_ref="test:owner",
                decision="accept",
                summary="Conflicting acceptance.",
                feedback_intake=_owner_feedback(evidence),
            )
        self.assertEqual(raised.exception.code, "accepted_with_feedback")

    def test_request_repair_requires_feedback_intake(self) -> None:
        with self.assertRaises(HumanFeedbackValidationError) as raised:
            create_human_feedback(
                _evidence(),
                source_ref="test:owner",
                decision="request_repair",
                summary="A repair is requested but no bounded feedback was supplied.",
            )
        self.assertEqual(raised.exception.code, "repair_feedback_required")

    def test_request_repair_only_loops_owner_human_rejections_back_to_f0(self) -> None:
        evidence = _evidence()
        feedback = _owner_feedback(evidence)
        item = feedback["items"][0]
        item["authority"] = "deterministic_qa"
        item["deterministic_qa"] = {
            "rule": "structural.no_edge_contact",
            "category": "structural",
            "severity": "error",
        }
        item["human"] = None

        with self.assertRaises(HumanFeedbackValidationError) as raised:
            create_human_feedback(
                evidence,
                source_ref="test:owner",
                decision="request_repair",
                summary="Do not synthesize deterministic QA from owner judgment.",
                feedback_intake=feedback,
            )
        self.assertEqual(raised.exception.code, "invalid_feedback_authority")

    def test_request_repair_requires_explicit_human_rejection(self) -> None:
        evidence = _evidence()
        feedback = _owner_feedback(evidence)
        feedback["items"][0]["human"]["human_rejection"] = False

        with self.assertRaises(HumanFeedbackValidationError) as raised:
            create_human_feedback(
                evidence,
                source_ref="test:owner",
                decision="request_repair",
                summary="A non-rejection cannot request another repair cycle.",
                feedback_intake=feedback,
            )
        self.assertEqual(raised.exception.code, "repair_request_not_rejected")

    def test_feedback_loop_must_bind_exact_reviewed_after_png(self) -> None:
        evidence = _evidence()
        feedback = _owner_feedback(evidence)
        feedback["target"]["artifact_sha256"] = "0" * 64

        with self.assertRaises(HumanFeedbackValidationError) as raised:
            create_human_feedback(
                evidence,
                source_ref="test:owner",
                decision="request_repair",
                summary="Target mismatch must fail closed.",
                feedback_intake=feedback,
            )
        self.assertEqual(raised.exception.code, "feedback_artifact_mismatch")

    def test_validator_rejects_forged_evidence_manifest_digest(self) -> None:
        review = create_human_feedback(
            _evidence(),
            source_ref="test:owner",
            decision="accept",
            summary="Owner accepts the reviewed result.",
        )
        forged = copy.deepcopy(review)
        forged["evidence_manifest_sha256"] = "0" * 64

        with self.assertRaises(HumanFeedbackValidationError) as raised:
            validate_human_feedback(forged)
        self.assertEqual(raised.exception.code, "evidence_digest_mismatch")

    def test_validator_rejects_authority_promotion_or_composite_completion(self) -> None:
        review = create_human_feedback(
            _evidence(),
            source_ref="test:owner",
            decision="accept",
            summary="Owner accepts the reviewed result.",
        )
        forged_authority = copy.deepcopy(review)
        forged_authority["authority"]["vlm"] = "used"
        with self.assertRaises(HumanFeedbackValidationError) as raised:
            validate_human_feedback(forged_authority)
        self.assertEqual(raised.exception.code, "invalid_authority_boundary")

        forged_completion = copy.deepcopy(review)
        forged_completion["completion"]["composite_completion"] = "complete"
        with self.assertRaises(HumanFeedbackValidationError) as raised:
            validate_human_feedback(forged_completion)
        self.assertEqual(raised.exception.code, "completion_mismatch")


if __name__ == "__main__":
    unittest.main()
