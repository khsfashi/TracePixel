from __future__ import annotations

import json
from pathlib import Path

from tracepixel.repair import FEEDBACK_INTAKE_SCHEMA_V1, validate_feedback_intake


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "feedback-intake.v1.schema.json"
CORE_LANE_PATH = ROOT / "config" / "tracepixel.core-lane.json"


def _sample() -> dict[str, object]:
    return {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "checkpoint-asset",
            "task_id": "P7-F0-checkpoint",
            "canvas": {"width": 16, "height": 16},
            "artifact_sha256": None,
        },
        "items": [
            {
                "id": "qa",
                "authority": "deterministic_qa",
                "source_ref": "checkpoint:qa",
                "summary": "A deterministic QA finding remains machine evidence.",
                "stage_hint": "silhouette",
                "region_hint": {"x": 0, "y": 0, "width": 1, "height": 1},
                "deterministic_qa": {
                    "rule": "structural.no_edge_contact",
                    "category": "structural",
                    "severity": "error",
                },
                "human": None,
            },
            {
                "id": "owner",
                "authority": "owner_human",
                "source_ref": "checkpoint:owner",
                "summary": "Owner perception stays human evidence.",
                "stage_hint": None,
                "region_hint": None,
                "deterministic_qa": None,
                "human": {
                    "human_rejection": True,
                    "scores": [{"dimension": "recognizability", "value": 2}],
                },
            },
        ],
    }


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if schema.get("$id") != "urn:tracepixel:schema:feedback-intake:v1":
        raise SystemExit("P7-F0 schema id mismatch")
    if schema.get("additionalProperties") is not False:
        raise SystemExit("P7-F0 root schema must fail closed")

    validated = validate_feedback_intake(_sample())
    qa_item, owner_item = validated["items"]
    if qa_item["authority"] != "deterministic_qa" or qa_item["human"] is not None:
        raise SystemExit("P7-F0 deterministic authority boundary failed")
    if owner_item["authority"] != "owner_human" or owner_item["deterministic_qa"] is not None:
        raise SystemExit("P7-F0 human authority boundary failed")

    item_fields = set(schema["$defs"]["item"]["properties"])
    forbidden = {"affected_region", "repair_program", "changed_pixels", "all_rules_pass"}
    if item_fields & forbidden:
        raise SystemExit("P7-F0 crossed into later repair/localization authority")

    lane = json.loads(CORE_LANE_PATH.read_text(encoding="utf-8"))
    if lane.get("current") != "P7":
        raise SystemExit("P7-F0 checkpoint requires P7 as current core phase")
    if lane.get("current_child") not in {"P7-F0", "P7-F1"}:
        raise SystemExit("P7-F0 checkpoint only supports the F0 implementation/handoff boundary")
    if lane.get("active_issue") != 71:
        raise SystemExit("P7-F0 checkpoint requires active issue #71")

    print("P7-F0 feedback intake checkpoint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
