from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.model import (
    PIXEL_PROGRAM_SCHEMA_V1,
    SILHOUETTE_STAGE_ID_V1,
    SILHOUETTE_STAGE_SCHEMA_V1,
    SilhouetteStageV1,
    SilhouetteStageValidationError,
    validate_silhouette_stage,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "silhouette-stage.v1.schema.json"
)


def _valid_stage() -> SilhouetteStageV1:
    return {
        "schema": SILHOUETTE_STAGE_SCHEMA_V1,
        "stage": SILHOUETTE_STAGE_ID_V1,
        "program": {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 16, "height": 16},
            "operations": [
                {
                    "op": "set_pixels",
                    "pixels": [
                        [7, 2, 80, 96, 112, 255],
                        [8, 2, 80, 96, 112, 255],
                        [6, 3, 80, 96, 112, 255],
                        [7, 3, 80, 96, 112, 255],
                        [8, 3, 80, 96, 112, 255],
                        [9, 3, 80, 96, 112, 255],
                    ],
                }
            ],
        },
    }


class SilhouetteStageSchemaTests(unittest.TestCase):
    def test_schema_is_versioned_closed_and_reuses_pixel_program_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(SILHOUETTE_STAGE_SCHEMA_V1, "tracepixel.silhouette-stage.v1")
        self.assertEqual(SILHOUETTE_STAGE_ID_V1, "silhouette")
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:silhouette-stage:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], ["schema", "stage", "program"])
        self.assertEqual(schema["properties"]["program"]["$ref"], "pixel-program.v1.schema.json")
        self.assertEqual(json.loads(json.dumps(_valid_stage())), _valid_stage())

    def test_valid_stage_is_returned_without_copy_or_normalization(self) -> None:
        stage = _valid_stage()

        validated = validate_silhouette_stage(stage)

        self.assertIs(validated, stage)
        self.assertIs(validated["program"], stage["program"])

    def test_multiple_operations_and_duplicate_coordinates_are_allowed_when_flat(self) -> None:
        stage = _valid_stage()
        stage["program"]["operations"].append(
            {
                "op": "set_pixels",
                "pixels": [
                    [7, 2, 80, 96, 112, 255],
                    [5, 4, 80, 96, 112, 255],
                ],
            }
        )

        self.assertIs(validate_silhouette_stage(stage), stage)

    def test_nested_pixel_program_failure_is_rebased_under_program_path(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["program"]["operations"][0]["pixels"][0][0] = 16

        with self.assertRaises(SilhouetteStageValidationError) as caught:
            validate_silhouette_stage(stage)

        self.assertEqual(caught.exception.code, "invalid_program")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[0]")
        self.assertIn("invalid_coordinate", caught.exception.message)

    def test_stage_identity_is_exact(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["stage"] = "forms"  # type: ignore[typeddict-item]

        with self.assertRaises(SilhouetteStageValidationError) as caught:
            validate_silhouette_stage(stage)

        self.assertEqual(caught.exception.code, "invalid_stage")
        self.assertEqual(caught.exception.path, "$.stage")

    def test_unsupported_schema_is_rejected(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["schema"] = "tracepixel.silhouette-stage.v2"  # type: ignore[typeddict-item]

        with self.assertRaises(SilhouetteStageValidationError) as caught:
            validate_silhouette_stage(stage)

        self.assertEqual(caught.exception.code, "unsupported_schema")
        self.assertEqual(caught.exception.path, "$.schema")

    def test_silhouette_must_not_be_empty(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["program"]["operations"][0]["pixels"] = []

        with self.assertRaises(SilhouetteStageValidationError) as caught:
            validate_silhouette_stage(stage)

        self.assertEqual(caught.exception.code, "empty_silhouette")
        self.assertEqual(caught.exception.path, "$.program.operations")

    def test_silhouette_pixels_must_be_fully_opaque(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["program"]["operations"][0]["pixels"][2][5] = 254

        with self.assertRaises(SilhouetteStageValidationError) as caught:
            validate_silhouette_stage(stage)

        self.assertEqual(caught.exception.code, "invalid_silhouette_alpha")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[2][5]")

    def test_silhouette_uses_one_exact_flat_rgba_color(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["program"]["operations"][0]["pixels"][3][2] = 81

        with self.assertRaises(SilhouetteStageValidationError) as caught:
            validate_silhouette_stage(stage)

        self.assertEqual(caught.exception.code, "multiple_silhouette_colors")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[3]")

    def test_contract_fails_closed_and_does_not_pull_later_stage_fields_forward(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(frozenset(schema["properties"]), {"schema", "stage", "program"})

        stage = deepcopy(_valid_stage())
        stage["major_forms"] = []
        with self.assertRaises(SilhouetteStageValidationError) as caught:
            validate_silhouette_stage(stage)

        self.assertEqual(caught.exception.code, "invalid_fields")
        self.assertEqual(caught.exception.path, "$")


if __name__ == "__main__":
    unittest.main()
