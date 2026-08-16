from __future__ import annotations

import json
from pathlib import Path

from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    REPAIR_PLAN_SCHEMA_V1,
    create_repair_plan,
    localize_feedback_intake,
    validate_repair_plan,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "repair-plan.v1.schema.json"
CORE_LANE_PATH = ROOT / "config" / "tracepixel.core-lane.json"


def _localization() -> dict[str, object]:
    intake = {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "checkpoint-asset",
            "task_id": "P7-F2-checkpoint",
            "canvas": {"width": 16, "height": 16},
            "artifact_sha256": None,
        },
        "items": [
            {
                "id": "repairable",
                "authority": "deterministic_qa",
                "source_ref": "checkpoint:qa",
                "summary": "Explicit source scope allows a bounded repair proposal.",
                "stage_hint": "outline_cleanup",
                "region_hint": {"x": 10, "y": 4, "width": 4, "height": 4},
                "deterministic_qa": {
                    "rule": "structural.no_edge_contact",
                    "category": "structural",
                    "severity": "error",
                },
                "human": None,
            },
            {
                "id": "deferred-owner",
                "authority": "owner_human",
                "source_ref": "checkpoint:owner",
                "summary": "Human perception is retained without inventing pixel edits.",
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
    return localize_feedback_intake(intake)


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if schema.get("$id") != "urn:tracepixel:schema:repair-plan:v1":
        raise SystemExit("P7-F2 schema id mismatch")
    if schema.get("additionalProperties") is not False:
        raise SystemExit("P7-F2 root schema must fail closed")

    localization = _localization()
    plan = create_repair_plan(
        localization,
        [
            {
                "feedback_id": "repairable",
                "target_stage": "outline_cleanup",
                "program": {
                    "schema": "tracepixel.pixel-program.v1",
                    "canvas": {"width": 16, "height": 16},
                    "operations": [
                        {
                            "op": "set_pixels",
                            "pixels": [
                                [12, 6, 20, 20, 20, 255],
                                [11, 5, 30, 30, 30, 255],
                            ],
                        },
                        {
                            "op": "set_pixels",
                            "pixels": [[12, 6, 40, 40, 40, 255]],
                        },
                    ],
                },
                "defer_reason": None,
            },
            {
                "feedback_id": "deferred-owner",
                "target_stage": None,
                "program": None,
                "defer_reason": "No explicit repair pixels have been proposed for this owner feedback.",
            },
        ],
    )
    validate_repair_plan(plan)

    if plan["schema"] != REPAIR_PLAN_SCHEMA_V1:
        raise SystemExit("P7-F2 result schema mismatch")
    if plan["localization"] is not localization:
        raise SystemExit("P7-F2 must retain the exact validated F1 localization object")

    repair, deferred = plan["repairs"]
    if repair["target_stage"] != "outline_cleanup":
        raise SystemExit("P7-F2 repair target escaped or lost the explicit F1 stage scope")
    if repair["planned_operation_count"] != 1 or repair["planned_pixel_edit_count"] != 2:
        raise SystemExit("P7-F2 did not canonicalize repair cost")
    if repair["planned_region"] != {"x": 11, "y": 5, "width": 2, "height": 2}:
        raise SystemExit("P7-F2 planned region must be the exact canonical edit bounding box")
    if repair["repair_program"]["operations"][0]["pixels"] != [
        [11, 5, 30, 30, 30, 255],
        [12, 6, 40, 40, 40, 255],
    ]:
        raise SystemExit("P7-F2 canonical repair program must keep last writes in stable y/x order")

    if (
        deferred["disposition"] != "defer"
        or deferred["repair_program"] is not None
        or deferred["planned_pixel_edit_count"] != 0
    ):
        raise SystemExit("P7-F2 defer path must not manufacture a repair")

    repair_fields = set(schema["$defs"]["repair"]["properties"])
    forbidden = {
        "changed_pixels",
        "executed_program",
        "qa_result",
        "all_rules_pass",
        "before_artifact",
        "after_artifact",
    }
    if repair_fields & forbidden:
        raise SystemExit("P7-F2 crossed into F3/F4 execution or evidence authority")

    lane = json.loads(CORE_LANE_PATH.read_text(encoding="utf-8"))
    if lane.get("current") != "P7":
        raise SystemExit("P7-F2 checkpoint requires P7 as current core phase")
    if lane.get("current_child") not in {"P7-F2", "P7-F3", "P7-F4", "P7-F5"}:
        raise SystemExit("P7-F2 checkpoint only supports the F2-F4 implementation/handoff range")
    if lane.get("active_issue") != 71:
        raise SystemExit("P7-F2 checkpoint requires active issue #71")

    print("P7-F2 minimal repair plan checkpoint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
