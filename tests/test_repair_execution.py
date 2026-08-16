from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from tracepixel.qa import QA_POLICY_SCHEMA_V1, analyze_structural, evaluate_qa_policy
from tracepixel.raster import Canvas
from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    REPAIR_EXECUTION_SCHEMA_V1,
    RepairExecutionValidationError,
    create_repair_plan,
    execute_repair_plan,
    localize_feedback_intake,
    validate_repair_execution,
)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "repair-execution.v1.schema.json"


class _EdgeQaEvaluator:
    def evaluate(self, canvas: Canvas) -> dict[str, object]:
        policy = {
            "schema": QA_POLICY_SCHEMA_V1,
            "rules": [{"rule": "structural.no_edge_contact", "severity": "error"}],
        }
        return evaluate_qa_policy(policy, structural=analyze_structural(canvas))


class _InvalidQaEvaluator:
    def evaluate(self, canvas: Canvas) -> dict[str, object]:
        del canvas
        return {
            "schema": "tracepixel.qa-findings.v1",
            "findings": [
                {
                    "rule": "structural.no_edge_contact",
                    "category": "human",
                    "severity": "error",
                }
            ],
        }


def _plan() -> dict[str, object]:
    intake = {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "potion-red-01",
            "task_id": "P7-F3-test",
            "canvas": {"width": 4, "height": 4},
            "artifact_sha256": "3" * 64,
        },
        "items": [
            {
                "id": "edge-repair",
                "authority": "deterministic_qa",
                "source_ref": "qa:edge",
                "summary": "Visible pixels touch the left edge.",
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
                "id": "owner-deferred",
                "authority": "owner_human",
                "source_ref": "owner:review",
                "summary": "Style feedback has no explicit repair pixels.",
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
                "feedback_id": "owner-deferred",
                "target_stage": None,
                "program": None,
                "defer_reason": "Owner feedback has no explicit repair pixels yet.",
            },
        ],
    )


def _source_canvas() -> Canvas:
    canvas = Canvas(4, 4)
    canvas.set_pixels(
        [
            (0, 1, (255, 0, 0, 255)),
            (1, 1, (255, 0, 0, 255)),
        ]
    )
    return canvas


class RepairExecutionTests(unittest.TestCase):
    def test_schema_is_closed_versioned_and_composes_f2_and_q5_findings(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(REPAIR_EXECUTION_SCHEMA_V1, "tracepixel.repair-execution.v1")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:repair-execution:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["plan"]["$ref"],
            "urn:tracepixel:schema:repair-plan:v1",
        )
        self.assertEqual(
            schema["properties"]["qa"]["$ref"],
            "https://tracepixel.dev/schemas/qa-findings.v1.schema.json",
        )

    def test_execute_retains_exact_plan_measures_actual_change_and_reruns_qa(self) -> None:
        plan = _plan()
        canvas = _source_canvas()
        before = canvas.rgba_bytes()

        result = execute_repair_plan(plan, canvas=canvas, qa_evaluator=_EdgeQaEvaluator())

        self.assertIs(result["plan"], plan)
        self.assertIs(validate_repair_execution(result), result)
        self.assertEqual(result["source_rgba_sha256"], sha256(before).hexdigest())
        self.assertEqual(result["result_rgba_sha256"], sha256(canvas.rgba_bytes()).hexdigest())
        self.assertEqual(result["applied_operation_count"], 1)
        self.assertEqual(result["applied_pixel_edit_count"], 2)
        self.assertEqual(result["executions"][0]["observed_changed_pixel_count"], 1)
        self.assertEqual(result["observed_changed_pixel_count"], 1)
        self.assertTrue(result["unaffected_region_stable"])
        self.assertEqual(result["qa"]["findings"], [])
        self.assertEqual(canvas.get_pixel(0, 1), (0, 0, 0, 0))
        self.assertEqual(canvas.get_pixel(1, 1), (255, 0, 0, 255))

    def test_deferred_item_is_not_executed_or_charged(self) -> None:
        result = execute_repair_plan(
            _plan(),
            canvas=_source_canvas(),
            qa_evaluator=_EdgeQaEvaluator(),
        )
        deferred = result["executions"][1]
        self.assertEqual(deferred["status"], "deferred")
        self.assertIsNone(deferred["target_stage"])
        self.assertEqual(deferred["applied_operation_count"], 0)
        self.assertEqual(deferred["applied_pixel_edit_count"], 0)
        self.assertEqual(deferred["observed_changed_pixel_count"], 0)

    def test_global_changed_count_is_source_to_result_not_sum_of_item_changes(self) -> None:
        plan = _plan()
        second_localization = deepcopy(plan["localization"])
        second_localization["intake"]["items"][1] = {
            "id": "restore",
            "authority": "deterministic_qa",
            "source_ref": "qa:restore",
            "summary": "Explicit second repair overlaps the first repair coordinate.",
            "stage_hint": "silhouette",
            "region_hint": {"x": 0, "y": 1, "width": 1, "height": 1},
            "deterministic_qa": {
                "rule": "structural.no_edge_contact",
                "category": "structural",
                "severity": "warning",
            },
            "human": None,
        }
        second_localization["localizations"][1] = {
            "feedback_id": "restore",
            "affected_stages": ["silhouette"],
            "stage_basis": "source_hint",
            "affected_region": {"x": 0, "y": 1, "width": 1, "height": 1},
            "region_basis": "source_hint",
        }
        overlapping = create_repair_plan(
            second_localization,
            [
                {
                    "feedback_id": "edge-repair",
                    "target_stage": "silhouette",
                    "program": {
                        "schema": "tracepixel.pixel-program.v1",
                        "canvas": {"width": 4, "height": 4},
                        "operations": [{"op": "set_pixels", "pixels": [[0, 1, 0, 0, 0, 0]]}],
                    },
                    "defer_reason": None,
                },
                {
                    "feedback_id": "restore",
                    "target_stage": "silhouette",
                    "program": {
                        "schema": "tracepixel.pixel-program.v1",
                        "canvas": {"width": 4, "height": 4},
                        "operations": [
                            {"op": "set_pixels", "pixels": [[0, 1, 255, 0, 0, 255]]}
                        ],
                    },
                    "defer_reason": None,
                },
            ],
        )

        result = execute_repair_plan(
            overlapping,
            canvas=_source_canvas(),
            qa_evaluator=_EdgeQaEvaluator(),
        )
        self.assertEqual(
            [item["observed_changed_pixel_count"] for item in result["executions"]],
            [1, 1],
        )
        self.assertEqual(result["observed_changed_pixel_count"], 0)
        self.assertEqual(result["source_rgba_sha256"], result["result_rgba_sha256"])
        self.assertTrue(result["unaffected_region_stable"])
        self.assertEqual(
            result["qa"]["findings"],
            [
                {
                    "rule": "structural.no_edge_contact",
                    "category": "structural",
                    "severity": "error",
                }
            ],
        )

    def test_canvas_dimensions_must_match_f0_target(self) -> None:
        with self.assertRaises(RepairExecutionValidationError) as caught:
            execute_repair_plan(
                _plan(),
                canvas=Canvas(5, 4),
                qa_evaluator=_EdgeQaEvaluator(),
            )
        self.assertEqual(caught.exception.code, "canvas_mismatch")

    def test_reqa_rejects_non_deterministic_or_malformed_findings_shape(self) -> None:
        with self.assertRaises(RepairExecutionValidationError) as caught:
            execute_repair_plan(
                _plan(),
                canvas=_source_canvas(),
                qa_evaluator=_InvalidQaEvaluator(),
            )
        self.assertEqual(caught.exception.code, "qa_category_mismatch")

    def test_validator_rejects_forged_execution_cost_and_order(self) -> None:
        result = execute_repair_plan(
            _plan(),
            canvas=_source_canvas(),
            qa_evaluator=_EdgeQaEvaluator(),
        )

        wrong_cost = deepcopy(result)
        wrong_cost["executions"][0]["applied_pixel_edit_count"] = 99
        with self.assertRaises(RepairExecutionValidationError) as caught:
            validate_repair_execution(wrong_cost)
        self.assertEqual(caught.exception.code, "applied_cost_mismatch")

        wrong_order = deepcopy(result)
        wrong_order["executions"][0]["feedback_id"] = "owner-deferred"
        with self.assertRaises(RepairExecutionValidationError) as caught:
            validate_repair_execution(wrong_order)
        self.assertEqual(caught.exception.code, "feedback_order_mismatch")

    def test_f3_does_not_cross_into_before_after_or_human_completion(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        root_fields = frozenset(schema["properties"])
        forbidden = {
            "all_rules_pass",
            "before_artifact",
            "after_artifact",
            "before_preview",
            "after_preview",
            "human_approval",
            "perceptual_score",
        }
        self.assertFalse(root_fields & forbidden)


if __name__ == "__main__":
    unittest.main()
