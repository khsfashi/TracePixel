from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.model import (
    MAJOR_FORMS_STAGE_ID_V1,
    MAJOR_FORMS_STAGE_SCHEMA_V1,
    MAX_MAJOR_FORMS_V1,
    PIXEL_PROGRAM_SCHEMA_V1,
    MajorFormsStageV1,
    MajorFormsStageValidationError,
    validate_major_forms_stage,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "major-forms-stage.v1.schema.json"
)


def _valid_stage() -> MajorFormsStageV1:
    return {
        "schema": MAJOR_FORMS_STAGE_SCHEMA_V1,
        "stage": MAJOR_FORMS_STAGE_ID_V1,
        "forms": [
            {"id": "body"},
            {"id": "cap"},
        ],
        "program": {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 16, "height": 16},
            "operations": [
                {
                    "op": "set_pixels",
                    "pixels": [
                        [6, 5, 80, 96, 112, 255],
                        [7, 5, 80, 96, 112, 255],
                        [8, 5, 80, 96, 112, 255],
                        [9, 5, 80, 96, 112, 255],
                    ],
                },
                {
                    "op": "set_pixels",
                    "pixels": [
                        [7, 3, 160, 176, 192, 255],
                        [8, 3, 160, 176, 192, 255],
                        [6, 4, 160, 176, 192, 255],
                        [7, 4, 160, 176, 192, 255],
                        [8, 4, 160, 176, 192, 255],
                        [9, 4, 160, 176, 192, 255],
                    ],
                },
            ],
        },
    }


class MajorFormsStageSchemaTests(unittest.TestCase):
    def test_schema_is_versioned_closed_bounded_and_reuses_pixel_program_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(MAJOR_FORMS_STAGE_SCHEMA_V1, "tracepixel.major-forms-stage.v1")
        self.assertEqual(MAJOR_FORMS_STAGE_ID_V1, "major_forms")
        self.assertEqual(MAX_MAJOR_FORMS_V1, 16)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:major-forms-stage:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], ["schema", "stage", "forms", "program"])
        self.assertEqual(schema["properties"]["forms"]["maxItems"], MAX_MAJOR_FORMS_V1)
        self.assertEqual(
            schema["properties"]["program"]["$ref"],
            "pixel-program.v1.schema.json",
        )
        self.assertEqual(json.loads(json.dumps(_valid_stage())), _valid_stage())

    def test_valid_stage_is_returned_without_copy_or_normalization(self) -> None:
        stage = _valid_stage()

        validated = validate_major_forms_stage(stage)

        self.assertIs(validated, stage)
        self.assertIs(validated["forms"], stage["forms"])
        self.assertIs(validated["program"], stage["program"])

    def test_form_order_is_positional_operation_identity_and_colors_may_differ(self) -> None:
        stage = _valid_stage()

        self.assertIs(validate_major_forms_stage(stage), stage)
        self.assertEqual(stage["forms"][0]["id"], "body")
        self.assertEqual(stage["forms"][1]["id"], "cap")

    def test_duplicate_coordinates_are_allowed_inside_and_across_forms(self) -> None:
        stage = _valid_stage()
        stage["program"]["operations"][0]["pixels"].append(
            [6, 5, 80, 96, 112, 255]
        )
        stage["program"]["operations"][1]["pixels"].append(
            [6, 5, 160, 176, 192, 255]
        )

        self.assertIs(validate_major_forms_stage(stage), stage)

    def test_nested_pixel_program_failure_is_rebased_under_program_path(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["program"]["operations"][0]["pixels"][0][0] = 16

        with self.assertRaises(MajorFormsStageValidationError) as caught:
            validate_major_forms_stage(stage)

        self.assertEqual(caught.exception.code, "invalid_program")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[0]")
        self.assertIn("invalid_coordinate", caught.exception.message)

    def test_form_ids_are_unique_bounded_ascii_slugs(self) -> None:
        invalid_cases = (
            ("Body", "invalid_form_id"),
            ("body part", "invalid_form_id"),
            ("1body", "invalid_form_id"),
            ("body/part", "invalid_form_id"),
            ("a" * 33, "invalid_form_id"),
        )
        for form_id, code in invalid_cases:
            with self.subTest(form_id=form_id):
                stage = deepcopy(_valid_stage())
                stage["forms"][0]["id"] = form_id
                with self.assertRaises(MajorFormsStageValidationError) as caught:
                    validate_major_forms_stage(stage)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.path, "$.forms[0].id")

        duplicate = deepcopy(_valid_stage())
        duplicate["forms"][1]["id"] = "body"
        with self.assertRaises(MajorFormsStageValidationError) as caught:
            validate_major_forms_stage(duplicate)
        self.assertEqual(caught.exception.code, "duplicate_form_id")
        self.assertEqual(caught.exception.path, "$.forms[1].id")

    def test_form_count_is_bounded_and_matches_program_operations(self) -> None:
        empty = deepcopy(_valid_stage())
        empty["forms"] = []
        with self.assertRaises(MajorFormsStageValidationError) as caught:
            validate_major_forms_stage(empty)
        self.assertEqual(caught.exception.code, "empty_major_forms")
        self.assertEqual(caught.exception.path, "$.forms")

        too_many = deepcopy(_valid_stage())
        too_many["forms"] = [{"id": f"form-{index}"} for index in range(17)]
        with self.assertRaises(MajorFormsStageValidationError) as caught:
            validate_major_forms_stage(too_many)
        self.assertEqual(caught.exception.code, "too_many_major_forms")
        self.assertEqual(caught.exception.path, "$.forms")

        mismatch = deepcopy(_valid_stage())
        mismatch["forms"].pop()
        with self.assertRaises(MajorFormsStageValidationError) as caught:
            validate_major_forms_stage(mismatch)
        self.assertEqual(caught.exception.code, "form_operation_mismatch")
        self.assertEqual(caught.exception.path, "$.forms")

    def test_each_form_operation_is_non_empty_fully_opaque_and_flat(self) -> None:
        empty = deepcopy(_valid_stage())
        empty["program"]["operations"][0]["pixels"] = []
        with self.assertRaises(MajorFormsStageValidationError) as caught:
            validate_major_forms_stage(empty)
        self.assertEqual(caught.exception.code, "empty_major_form")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels")

        translucent = deepcopy(_valid_stage())
        translucent["program"]["operations"][1]["pixels"][0][5] = 254
        with self.assertRaises(MajorFormsStageValidationError) as caught:
            validate_major_forms_stage(translucent)
        self.assertEqual(caught.exception.code, "invalid_major_form_alpha")
        self.assertEqual(caught.exception.path, "$.program.operations[1].pixels[0][5]")

        multicolor = deepcopy(_valid_stage())
        multicolor["program"]["operations"][0]["pixels"][1][2] = 81
        with self.assertRaises(MajorFormsStageValidationError) as caught:
            validate_major_forms_stage(multicolor)
        self.assertEqual(caught.exception.code, "multiple_major_form_colors")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[1]")

    def test_contract_fails_closed_and_does_not_pull_palette_fields_forward(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            frozenset(schema["properties"]),
            {"schema", "stage", "forms", "program"},
        )

        stage = deepcopy(_valid_stage())
        stage["palette"] = []
        with self.assertRaises(MajorFormsStageValidationError) as caught:
            validate_major_forms_stage(stage)

        self.assertEqual(caught.exception.code, "invalid_fields")
        self.assertEqual(caught.exception.path, "$")


if __name__ == "__main__":
    unittest.main()
