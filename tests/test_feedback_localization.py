from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.model.stage_plan import STAGE_SEQUENCE_V1
from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    FEEDBACK_LOCALIZATION_SCHEMA_V1,
    FeedbackLocalizationValidationError,
    localize_feedback_intake,
    validate_feedback_localization,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "feedback-localization.v1.schema.json"
)


def _intake() -> dict[str, object]:
    return {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "potion-red-01",
            "task_id": "P7-F1-test",
            "canvas": {"width": 16, "height": 12},
            "artifact_sha256": "1" * 64,
        },
        "items": [
            {
                "id": "qa-hinted",
                "authority": "deterministic_qa",
                "source_ref": "qa:edge",
                "summary": "Visible pixels touch the left edge.",
                "stage_hint": "silhouette",
                "region_hint": {"x": 0, "y": 2, "width": 2, "height": 6},
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


class FeedbackLocalizationTests(unittest.TestCase):
    def test_schema_is_closed_versioned_and_composes_f0(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(FEEDBACK_LOCALIZATION_SCHEMA_V1, "tracepixel.feedback-localization.v1")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:feedback-localization:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["intake"]["$ref"],
            "urn:tracepixel:schema:feedback-intake:v1",
        )
        self.assertFalse(schema["$defs"]["localization"]["additionalProperties"])

    def test_localization_retains_the_exact_validated_intake_object(self) -> None:
        intake = _intake()
        localized = localize_feedback_intake(intake)
        self.assertIs(localized["intake"], intake)
        self.assertIs(validate_feedback_localization(localized), localized)

    def test_explicit_source_hints_become_exact_reviewable_scopes(self) -> None:
        localized = localize_feedback_intake(_intake())
        item = localized["localizations"][0]
        self.assertEqual(item["feedback_id"], "qa-hinted")
        self.assertEqual(item["affected_stages"], ["silhouette"])
        self.assertEqual(item["stage_basis"], "source_hint")
        self.assertEqual(
            item["affected_region"],
            {"x": 0, "y": 2, "width": 2, "height": 6},
        )
        self.assertEqual(item["region_basis"], "source_hint")

    def test_missing_hints_use_conservative_full_scopes_without_guessing(self) -> None:
        localized = localize_feedback_intake(_intake())
        item = localized["localizations"][1]
        self.assertEqual(item["affected_stages"], list(STAGE_SEQUENCE_V1))
        self.assertEqual(item["stage_basis"], "full_pipeline_fallback")
        self.assertEqual(
            item["affected_region"],
            {"x": 0, "y": 0, "width": 16, "height": 12},
        )
        self.assertEqual(item["region_basis"], "full_canvas_fallback")

    def test_prose_scores_and_qa_rule_do_not_create_false_precision(self) -> None:
        first = _intake()
        second = deepcopy(first)
        second["items"][1]["summary"] = "Outline, palette, pose, and details all feel wrong."
        second["items"][1]["human"]["scores"] = [
            {"dimension": "recognizability", "value": 1},
            {"dimension": "style_coherence", "value": 1},
        ]
        second["items"][0]["deterministic_qa"]["rule"] = "connectivity.single_component"
        second["items"][0]["deterministic_qa"]["category"] = "connectivity"

        first_localized = localize_feedback_intake(first)
        second_localized = localize_feedback_intake(second)
        self.assertEqual(
            first_localized["localizations"][1],
            second_localized["localizations"][1],
        )
        self.assertEqual(
            first_localized["localizations"][0]["affected_stages"],
            second_localized["localizations"][0]["affected_stages"],
        )

    def test_localization_count_and_order_are_bound_to_source_items(self) -> None:
        localized = localize_feedback_intake(_intake())
        localized["localizations"].reverse()
        with self.assertRaises(FeedbackLocalizationValidationError) as caught:
            validate_feedback_localization(localized)
        self.assertEqual(caught.exception.code, "feedback_order_mismatch")

    def test_cannot_narrow_a_fallback_scope_without_source_evidence(self) -> None:
        localized = localize_feedback_intake(_intake())
        localized["localizations"][1]["affected_stages"] = ["semantic_details"]
        localized["localizations"][1]["stage_basis"] = "source_hint"
        with self.assertRaises(FeedbackLocalizationValidationError) as caught:
            validate_feedback_localization(localized)
        self.assertEqual(caught.exception.code, "stage_scope_mismatch")

        localized = localize_feedback_intake(_intake())
        localized["localizations"][1]["affected_region"] = {
            "x": 4,
            "y": 4,
            "width": 2,
            "height": 2,
        }
        with self.assertRaises(FeedbackLocalizationValidationError) as caught:
            validate_feedback_localization(localized)
        self.assertEqual(caught.exception.code, "region_scope_mismatch")

    def test_stage_scope_must_be_unique_and_in_canonical_order(self) -> None:
        localized = localize_feedback_intake(_intake())
        localized["localizations"][1]["affected_stages"] = ["major_forms", "silhouette"]
        with self.assertRaises(FeedbackLocalizationValidationError) as caught:
            validate_feedback_localization(localized)
        self.assertEqual(caught.exception.code, "invalid_stage_order")

        localized = localize_feedback_intake(_intake())
        localized["localizations"][1]["affected_stages"] = ["silhouette", "silhouette"]
        with self.assertRaises(FeedbackLocalizationValidationError) as caught:
            validate_feedback_localization(localized)
        self.assertEqual(caught.exception.code, "duplicate_stage")

    def test_f1_does_not_cross_into_repair_or_execution(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        localization_fields = frozenset(schema["$defs"]["localization"]["properties"])
        self.assertNotIn("repair_program", localization_fields)
        self.assertNotIn("changed_pixels", localization_fields)
        self.assertNotIn("all_rules_pass", localization_fields)
        self.assertNotIn("reexecution", localization_fields)


if __name__ == "__main__":
    unittest.main()
