from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    REPAIR_PLAN_SCHEMA_V1,
    RepairPlanValidationError,
    create_repair_plan,
    localize_feedback_intake,
    validate_repair_plan,
)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "repair-plan.v1.schema.json"


def _localization() -> dict[str, object]:
    intake = {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "potion-red-01",
            "task_id": "P7-F2-test",
            "canvas": {"width": 16, "height": 12},
            "artifact_sha256": "2" * 64,
        },
        "items": [
            {
                "id": "qa-hinted",
                "authority": "deterministic_qa",
                "source_ref": "qa:edge",
                "summary": "Visible pixels touch the left edge.",
                "stage_hint": "silhouette",
                "region_hint": {"x": 1, "y": 2, "width": 5, "height": 5},
                "deterministic_qa": {
                    "rule": "structural.no_edge_contact",
                    "category": "structural",
                    "severity": "error",
                },
                "human": None,
            },
            {
                "id": "owner-unhinted",
                "authority": "owner_human",
                "source_ref": "owner:review-7",
                "summary": "It is hard to read at native size.",
                "stage_hint": None,
                "region_hint": None,
                "deterministic_qa": None,
                "human": {
                    "human_rejection": True,
                    "scores": [{"dimension": "native_1x_readability", "value": 2}],
                },
            },
        ],
    }
    return localize_feedback_intake(intake)


def _program(*operations: list[list[int]]) -> dict[str, object]:
    return {
        "schema": "tracepixel.pixel-program.v1",
        "canvas": {"width": 16, "height": 12},
        "operations": [{"op": "set_pixels", "pixels": pixels} for pixels in operations],
    }


def _proposals() -> list[dict[str, object]]:
    return [
        {
            "feedback_id": "qa-hinted",
            "target_stage": "silhouette",
            "program": _program(
                [
                    [4, 4, 255, 0, 0, 255],
                    [2, 3, 255, 0, 0, 255],
                ],
                [
                    [4, 4, 128, 0, 0, 255],
                    [3, 5, 255, 0, 0, 255],
                ],
            ),
            "defer_reason": None,
        },
        {
            "feedback_id": "owner-unhinted",
            "target_stage": None,
            "program": None,
            "defer_reason": "Owner feedback has no explicit repair pixels yet.",
        },
    ]


class RepairPlanTests(unittest.TestCase):
    def test_schema_is_closed_versioned_and_composes_f1_and_pixel_program(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(REPAIR_PLAN_SCHEMA_V1, "tracepixel.repair-plan.v1")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:repair-plan:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["localization"]["$ref"],
            "urn:tracepixel:schema:feedback-localization:v1",
        )
        repair_program = schema["$defs"]["repair"]["properties"]["repair_program"]
        self.assertEqual(
            repair_program["oneOf"][0]["$ref"],
            "urn:tracepixel:schema:pixel-program:v1",
        )

    def test_builder_retains_exact_f1_object_and_validates_closed_plan(self) -> None:
        localization = _localization()
        plan = create_repair_plan(localization, _proposals())
        self.assertIs(plan["localization"], localization)
        self.assertIs(validate_repair_plan(plan), plan)

    def test_builder_canonicalizes_to_one_unique_stably_ordered_operation(self) -> None:
        plan = create_repair_plan(_localization(), _proposals())
        repair = plan["repairs"][0]
        self.assertEqual(repair["disposition"], "repair")
        self.assertEqual(repair["target_stage"], "silhouette")
        self.assertEqual(repair["planned_operation_count"], 1)
        self.assertEqual(repair["planned_pixel_edit_count"], 3)
        self.assertEqual(
            repair["planned_region"],
            {"x": 2, "y": 3, "width": 3, "height": 3},
        )
        self.assertEqual(
            repair["repair_program"]["operations"],
            [
                {
                    "op": "set_pixels",
                    "pixels": [
                        [2, 3, 255, 0, 0, 255],
                        [4, 4, 128, 0, 0, 255],
                        [3, 5, 255, 0, 0, 255],
                    ],
                }
            ],
        )

    def test_repair_cannot_target_stage_outside_f1_scope(self) -> None:
        proposals = _proposals()
        proposals[0]["target_stage"] = "outline_cleanup"
        with self.assertRaises(RepairPlanValidationError) as caught:
            create_repair_plan(_localization(), proposals)
        self.assertEqual(caught.exception.code, "stage_outside_localization")

    def test_repair_pixels_cannot_escape_f1_region(self) -> None:
        proposals = _proposals()
        proposals[0]["program"] = _program([[8, 8, 255, 0, 0, 255]])
        with self.assertRaises(RepairPlanValidationError) as caught:
            create_repair_plan(_localization(), proposals)
        self.assertEqual(caught.exception.code, "pixel_outside_localization")

    def test_defer_requires_no_stage_or_program_and_reports_zero_cost(self) -> None:
        plan = create_repair_plan(_localization(), _proposals())
        deferred = plan["repairs"][1]
        self.assertEqual(deferred["disposition"], "defer")
        self.assertIsNone(deferred["target_stage"])
        self.assertIsNone(deferred["planned_region"])
        self.assertIsNone(deferred["repair_program"])
        self.assertEqual(deferred["planned_operation_count"], 0)
        self.assertEqual(deferred["planned_pixel_edit_count"], 0)
        self.assertTrue(deferred["defer_reason"])

    def test_validator_rejects_noncanonical_or_forged_planned_cost(self) -> None:
        plan = create_repair_plan(_localization(), _proposals())
        nonminimal = deepcopy(plan)
        pixels = nonminimal["repairs"][0]["repair_program"]["operations"][0]["pixels"]
        nonminimal["repairs"][0]["repair_program"]["operations"] = [
            {"op": "set_pixels", "pixels": pixels[:1]},
            {"op": "set_pixels", "pixels": pixels[1:]},
        ]
        with self.assertRaises(RepairPlanValidationError) as caught:
            validate_repair_plan(nonminimal)
        self.assertEqual(caught.exception.code, "nonminimal_program")

        wrong_cost = deepcopy(plan)
        wrong_cost["repairs"][0]["planned_pixel_edit_count"] = 99
        with self.assertRaises(RepairPlanValidationError) as caught:
            validate_repair_plan(wrong_cost)
        self.assertEqual(caught.exception.code, "planned_cost_mismatch")

        wrong_region = deepcopy(plan)
        wrong_region["repairs"][0]["planned_region"]["width"] += 1
        with self.assertRaises(RepairPlanValidationError) as caught:
            validate_repair_plan(wrong_region)
        self.assertEqual(caught.exception.code, "planned_region_mismatch")

    def test_f2_does_not_cross_into_execution_reqa_or_before_after_evidence(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        repair_fields = frozenset(schema["$defs"]["repair"]["properties"])
        forbidden = {
            "changed_pixels",
            "executed_program",
            "qa_result",
            "all_rules_pass",
            "before_artifact",
            "after_artifact",
        }
        self.assertFalse(repair_fields & forbidden)


if __name__ == "__main__":
    unittest.main()
