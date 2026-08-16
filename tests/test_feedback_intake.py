from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    MAX_FEEDBACK_ITEMS_V1,
    FeedbackIntakeV1,
    FeedbackIntakeValidationError,
    validate_feedback_intake,
)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "feedback-intake.v1.schema.json"


def _valid_intake() -> FeedbackIntakeV1:
    return {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "potion-red-01",
            "task_id": "P7-DEMO-01",
            "canvas": {"width": 16, "height": 16},
            "artifact_sha256": "1" * 64,
        },
        "items": [
            {
                "id": "qa-01",
                "authority": "deterministic_qa",
                "source_ref": "qa-findings:rule-0",
                "summary": "Visible pixels touch an outer edge.",
                "stage_hint": "silhouette",
                "region_hint": {"x": 0, "y": 3, "width": 2, "height": 7},
                "deterministic_qa": {
                    "rule": "structural.no_edge_contact",
                    "category": "structural",
                    "severity": "error",
                },
                "human": None,
            },
            {
                "id": "owner-01",
                "authority": "owner_human",
                "source_ref": "owner-review:artifact-07",
                "summary": "The object reads like a blob at native 1x.",
                "stage_hint": "major_forms",
                "region_hint": None,
                "deterministic_qa": None,
                "human": {
                    "human_rejection": True,
                    "scores": [
                        {"dimension": "recognizability", "value": 2},
                        {"dimension": "native_1x_readability", "value": 2},
                    ],
                },
            },
        ],
    }


class FeedbackIntakeTests(unittest.TestCase):
    def test_schema_is_closed_versioned_and_bounded(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(FEEDBACK_INTAKE_SCHEMA_V1, "tracepixel.feedback-intake.v1")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:feedback-intake:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["items"]["maxItems"], MAX_FEEDBACK_ITEMS_V1)
        self.assertFalse(schema["$defs"]["item"]["additionalProperties"])

    def test_valid_intake_is_returned_without_copy_or_normalization(self) -> None:
        intake = _valid_intake()
        self.assertIs(validate_feedback_intake(intake), intake)

    def test_machine_and_human_authority_payloads_are_mutually_exclusive(self) -> None:
        intake = deepcopy(_valid_intake())
        intake["items"][1]["deterministic_qa"] = {
            "rule": "structural.non_empty",
            "category": "structural",
            "severity": "error",
        }
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "authority_payload_mismatch")
        self.assertEqual(caught.exception.path, "$.items[1]")

    def test_human_feedback_can_be_prose_only_without_becoming_qa(self) -> None:
        intake = deepcopy(_valid_intake())
        intake["items"][1]["human"] = {"human_rejection": None, "scores": []}
        self.assertIs(validate_feedback_intake(intake), intake)
        self.assertIsNone(intake["items"][1]["deterministic_qa"])

    def test_qa_rule_category_pair_must_be_consistent(self) -> None:
        intake = deepcopy(_valid_intake())
        assert intake["items"][0]["deterministic_qa"] is not None
        intake["items"][0]["deterministic_qa"]["category"] = "color"
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "qa_category_mismatch")
        self.assertEqual(caught.exception.path, "$.items[0].deterministic_qa.category")

    def test_region_hint_must_fit_target_canvas(self) -> None:
        intake = deepcopy(_valid_intake())
        intake["items"][0]["region_hint"] = {"x": 15, "y": 0, "width": 2, "height": 1}
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "invalid_region")
        self.assertEqual(caught.exception.path, "$.items[0].region_hint")

    def test_stage_hint_is_limited_to_existing_p3_stage_ids(self) -> None:
        intake = deepcopy(_valid_intake())
        intake["items"][0]["stage_hint"] = "final_polish"  # type: ignore[typeddict-item]
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "invalid_stage_hint")

    def test_owner_scores_are_bounded_and_unique(self) -> None:
        intake = deepcopy(_valid_intake())
        assert intake["items"][1]["human"] is not None
        intake["items"][1]["human"]["scores"] = [
            {"dimension": "recognizability", "value": 2},
            {"dimension": "recognizability", "value": 3},
        ]
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "duplicate_score_dimension")

        intake = deepcopy(_valid_intake())
        assert intake["items"][1]["human"] is not None
        intake["items"][1]["human"]["scores"][0]["value"] = 0
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "invalid_score")

    def test_item_count_and_ids_are_bounded(self) -> None:
        intake = deepcopy(_valid_intake())
        intake["items"] = []
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "invalid_item_count")

        intake = deepcopy(_valid_intake())
        intake["items"][1]["id"] = intake["items"][0]["id"]
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "duplicate_item_id")

    def test_target_identity_and_artifact_digest_are_explicit(self) -> None:
        intake = deepcopy(_valid_intake())
        intake["target"]["artifact_sha256"] = "ABC"
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "invalid_sha256")

        intake = deepcopy(_valid_intake())
        intake["target"]["artifact_sha256"] = None
        self.assertIs(validate_feedback_intake(intake), intake)

    def test_missing_or_extra_fields_fail_closed(self) -> None:
        intake = deepcopy(_valid_intake())
        del intake["items"][0]["stage_hint"]
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "invalid_fields")

        intake = deepcopy(_valid_intake())
        intake["items"][0]["repair_program"] = {}  # type: ignore[typeddict-unknown-key]
        with self.assertRaises(FeedbackIntakeValidationError) as caught:
            validate_feedback_intake(intake)
        self.assertEqual(caught.exception.code, "invalid_fields")

    def test_f0_does_not_smuggle_localization_or_repair_execution(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        item_fields = frozenset(schema["$defs"]["item"]["properties"])
        self.assertNotIn("affected_region", item_fields)
        self.assertNotIn("repair_program", item_fields)
        self.assertNotIn("changed_pixels", item_fields)
        self.assertNotIn("all_rules_pass", item_fields)


if __name__ == "__main__":
    unittest.main()
