from __future__ import annotations

import json
from pathlib import Path

from tracepixel.model.stage_plan import STAGE_SEQUENCE_V1
from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    FEEDBACK_LOCALIZATION_SCHEMA_V1,
    localize_feedback_intake,
    validate_feedback_localization,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "feedback-localization.v1.schema.json"
CORE_LANE_PATH = ROOT / "config" / "tracepixel.core-lane.json"


def _sample() -> dict[str, object]:
    return {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "checkpoint-asset",
            "task_id": "P7-F1-checkpoint",
            "canvas": {"width": 16, "height": 16},
            "artifact_sha256": None,
        },
        "items": [
            {
                "id": "hinted",
                "authority": "deterministic_qa",
                "source_ref": "checkpoint:qa",
                "summary": "The source provided an explicit scope hint.",
                "stage_hint": "outline_cleanup",
                "region_hint": {"x": 12, "y": 4, "width": 2, "height": 3},
                "deterministic_qa": {
                    "rule": "structural.no_edge_contact",
                    "category": "structural",
                    "severity": "error",
                },
                "human": None,
            },
            {
                "id": "unhinted-owner",
                "authority": "owner_human",
                "source_ref": "checkpoint:owner",
                "summary": "Human perception has no machine-proven localization.",
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
    if schema.get("$id") != "urn:tracepixel:schema:feedback-localization:v1":
        raise SystemExit("P7-F1 schema id mismatch")
    if schema.get("additionalProperties") is not False:
        raise SystemExit("P7-F1 root schema must fail closed")

    intake = _sample()
    localized = localize_feedback_intake(intake)
    validate_feedback_localization(localized)
    if localized["schema"] != FEEDBACK_LOCALIZATION_SCHEMA_V1:
        raise SystemExit("P7-F1 result schema mismatch")
    if localized["intake"] is not intake:
        raise SystemExit("P7-F1 must retain the exact validated F0 intake object")

    hinted, fallback = localized["localizations"]
    if hinted["affected_stages"] != ["outline_cleanup"] or hinted["stage_basis"] != "source_hint":
        raise SystemExit("P7-F1 did not preserve explicit stage hint")
    if hinted["affected_region"] != {"x": 12, "y": 4, "width": 2, "height": 3}:
        raise SystemExit("P7-F1 did not preserve explicit region hint")
    if fallback["affected_stages"] != list(STAGE_SEQUENCE_V1):
        raise SystemExit("P7-F1 missing-stage fallback must cover the complete P3 pipeline")
    if fallback["affected_region"] != {"x": 0, "y": 0, "width": 16, "height": 16}:
        raise SystemExit("P7-F1 missing-region fallback must cover the complete canvas")

    localization_fields = set(schema["$defs"]["localization"]["properties"])
    forbidden = {"repair_program", "changed_pixels", "all_rules_pass", "reexecution"}
    if localization_fields & forbidden:
        raise SystemExit("P7-F1 crossed into later repair/execution authority")

    lane = json.loads(CORE_LANE_PATH.read_text(encoding="utf-8"))
    if lane.get("current") != "P7":
        raise SystemExit("P7-F1 checkpoint requires P7 as current core phase")
    if lane.get("current_child") not in {"P7-F1", "P7-F2", "P7-F3"}:
        raise SystemExit("P7-F1 checkpoint only supports the F1/F2 implementation handoff range")
    if lane.get("active_issue") != 71:
        raise SystemExit("P7-F1 checkpoint requires active issue #71")

    print("P7-F1 feedback localization checkpoint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
