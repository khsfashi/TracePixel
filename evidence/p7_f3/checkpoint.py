from __future__ import annotations

import json
from pathlib import Path

from evidence.p7_lane import validate_p7_completion_lane
from tracepixel.qa import QA_POLICY_SCHEMA_V1, analyze_structural, evaluate_qa_policy
from tracepixel.raster import Canvas
from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    REPAIR_EXECUTION_SCHEMA_V1,
    create_repair_plan,
    execute_repair_plan,
    localize_feedback_intake,
    validate_repair_execution,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "repair-execution.v1.schema.json"
CORE_LANE_PATH = ROOT / "config" / "tracepixel.core-lane.json"


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
            "asset_id": "checkpoint-asset",
            "task_id": "P7-F3-checkpoint",
            "canvas": {"width": 4, "height": 4},
            "artifact_sha256": None,
        },
        "items": [
            {
                "id": "edge-repair",
                "authority": "deterministic_qa",
                "source_ref": "checkpoint:qa",
                "summary": "Move visible occupancy away from the left edge.",
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
                "source_ref": "checkpoint:owner",
                "summary": "Owner feedback remains deferred without explicit pixels.",
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
                "defer_reason": "No explicit owner repair pixels are available yet.",
            },
        ],
    )


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if schema.get("$id") != "urn:tracepixel:schema:repair-execution:v1":
        raise SystemExit("P7-F3 schema id mismatch")
    if schema.get("additionalProperties") is not False:
        raise SystemExit("P7-F3 root schema must fail closed")

    plan = _plan()
    canvas = Canvas(4, 4)
    canvas.set_pixels(
        [
            (0, 1, (255, 0, 0, 255)),
            (1, 1, (255, 0, 0, 255)),
        ]
    )

    before = canvas.rgba_bytes()
    result = execute_repair_plan(plan, canvas=canvas, qa_evaluator=_QaEvaluator())
    validate_repair_execution(result)

    if result["schema"] != REPAIR_EXECUTION_SCHEMA_V1:
        raise SystemExit("P7-F3 result schema mismatch")
    if result["plan"] is not plan:
        raise SystemExit("P7-F3 must retain the exact validated F2 plan object")
    if result["source_rgba_sha256"] == result["result_rgba_sha256"]:
        raise SystemExit("P7-F3 source/result digests must reflect the actual repair")
    if result["applied_operation_count"] != 1 or result["applied_pixel_edit_count"] != 2:
        raise SystemExit("P7-F3 applied cost did not match the canonical F2 program")
    if result["executions"][0]["observed_changed_pixel_count"] != 1:
        raise SystemExit("P7-F3 must distinguish applied edits from actual changed pixels")
    if result["observed_changed_pixel_count"] != 1:
        raise SystemExit("P7-F3 final changed-pixel accounting mismatch")
    if result["executions"][1]["status"] != "deferred":
        raise SystemExit("P7-F3 must preserve deferred items without executing them")
    if result["unaffected_region_stable"] is not True:
        raise SystemExit("P7-F3 changed pixels outside the exact F2 planned write set")
    if result["qa"]["findings"]:
        raise SystemExit("P7-F3 deterministic re-QA did not clear the edge-contact finding")

    after = canvas.rgba_bytes()
    changed_indices = [
        index
        for index in range(16)
        if before[index * 4 : index * 4 + 4] != after[index * 4 : index * 4 + 4]
    ]
    if changed_indices != [4]:
        raise SystemExit("P7-F3 checkpoint observed mutation outside the intended pixel")

    root_fields = set(schema["properties"])
    forbidden = {
        "all_rules_pass",
        "before_artifact",
        "after_artifact",
        "before_preview",
        "after_preview",
        "human_approval",
        "perceptual_score",
    }
    if root_fields & forbidden:
        raise SystemExit("P7-F3 crossed into F4/F5 visual or human evidence authority")

    lane = json.loads(CORE_LANE_PATH.read_text(encoding="utf-8"))
    validate_p7_completion_lane(lane, checkpoint_child="P7-F3")

    print("P7-F3 repair execution and deterministic re-QA checkpoint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
