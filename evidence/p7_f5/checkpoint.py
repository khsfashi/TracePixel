from __future__ import annotations

import json
from pathlib import Path

from evidence.p7_lane import validate_p7_completion_lane
from tracepixel.qa import QA_POLICY_SCHEMA_V1, analyze_structural, evaluate_qa_policy
from tracepixel.raster import Canvas
from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    HUMAN_FEEDBACK_SCHEMA_V1,
    build_repair_evidence,
    create_human_feedback,
    create_repair_plan,
    localize_feedback_intake,
    validate_human_feedback,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "human-feedback.v1.schema.json"
CORE_LANE_PATH = ROOT / "config" / "tracepixel.core-lane.json"


class _QaEvaluator:
    def evaluate(self, canvas: Canvas) -> dict[str, object]:
        policy = {
            "schema": QA_POLICY_SCHEMA_V1,
            "rules": [{"rule": "structural.no_edge_contact", "severity": "error"}],
        }
        return evaluate_qa_policy(policy, structural=analyze_structural(canvas))


def _evidence() -> dict[str, object]:
    intake = {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "p7-f5-checkpoint-asset",
            "task_id": "P7-F5-checkpoint",
            "canvas": {"width": 4, "height": 4},
            "artifact_sha256": None,
        },
        "items": [
            {
                "id": "edge-repair",
                "authority": "deterministic_qa",
                "source_ref": "checkpoint:qa",
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
    plan = create_repair_plan(
        localize_feedback_intake(intake),
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
    canvas = Canvas(4, 4)
    canvas.set_pixels(
        [
            (0, 1, (255, 0, 0, 255)),
            (1, 1, (255, 0, 0, 255)),
        ]
    )
    return build_repair_evidence(
        plan,
        canvas=canvas,
        qa_evaluator=_QaEvaluator(),
        preview_scale=8,
    ).manifest


def _repair_feedback(evidence: dict[str, object]) -> dict[str, object]:
    target = evidence["execution"]["plan"]["localization"]["intake"]["target"]
    return {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": target["asset_id"],
            "task_id": target["task_id"],
            "canvas": target["canvas"],
            "artifact_sha256": evidence["after_native_png"]["sha256"],
        },
        "items": [
            {
                "id": "owner-detail-request",
                "authority": "owner_human",
                "source_ref": "checkpoint:owner",
                "summary": "Structural QA is clear, but the owner requests a semantic-detail repair.",
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


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if schema.get("$id") != "urn:tracepixel:schema:human-feedback:v1":
        raise SystemExit("P7-F5 schema id mismatch")
    if schema.get("additionalProperties") is not False:
        raise SystemExit("P7-F5 root schema must fail closed")

    evidence = _evidence()
    if evidence["execution"]["qa"]["findings"]:
        raise SystemExit("P7-F5 checkpoint fixture must have deterministic QA clear")

    repair_requested = validate_human_feedback(
        create_human_feedback(
            evidence,
            source_ref="checkpoint:owner-review",
            decision="request_repair",
            summary="QA is clear, but human-visible authoring is not accepted yet.",
            feedback_intake=_repair_feedback(evidence),
        )
    )
    if repair_requested["schema"] != HUMAN_FEEDBACK_SCHEMA_V1:
        raise SystemExit("P7-F5 result schema mismatch")
    completion = repair_requested["completion"]
    if completion["deterministic_qa_status"] != "no-findings":
        raise SystemExit("P7-F5 lost exact deterministic QA status")
    if completion["human_authoring_status"] != "repair-requested":
        raise SystemExit("P7-F5 must permit human repair request after deterministic QA clears")
    if completion["composite_completion"] != "not-defined":
        raise SystemExit("P7-F5 must not synthesize composite completion")
    feedback = repair_requested["feedback_intake"]
    if feedback is None:
        raise SystemExit("P7-F5 repair request lost the bounded F0 feedback loop")
    if feedback["target"]["artifact_sha256"] != evidence["after_native_png"]["sha256"]:
        raise SystemExit("P7-F5 feedback loop is not bound to exact reviewed after/native.png bytes")

    accepted = validate_human_feedback(
        create_human_feedback(
            evidence,
            source_ref="checkpoint:owner-review",
            decision="accept",
            summary="Owner accepts the reviewed result.",
        )
    )
    if accepted["completion"]["human_authoring_status"] != "accepted":
        raise SystemExit("P7-F5 explicit acceptance was not retained")
    if accepted["feedback_intake"] is not None:
        raise SystemExit("P7-F5 accepted result must not request another repair loop")

    root_fields = set(schema["properties"])
    forbidden = {
        "all_rules_pass",
        "overall_complete",
        "composite_score",
        "vlm_verdict",
        "automatic_approval",
    }
    if root_fields & forbidden:
        raise SystemExit("P7-F5 schema introduced forbidden synthetic completion/perceptual authority")
    authority = repair_requested["authority"]
    if authority != {
        "human": "repository-owner",
        "deterministic_qa": "retained-not-overridden",
        "perceptual": "owner-human-only",
        "vlm": "not-used",
    }:
        raise SystemExit("P7-F5 authority boundary mismatch")

    lane = json.loads(CORE_LANE_PATH.read_text(encoding="utf-8"))
    validate_p7_completion_lane(lane, checkpoint_child="P7-F5")

    print("P7-F5 human feedback contract checkpoint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
