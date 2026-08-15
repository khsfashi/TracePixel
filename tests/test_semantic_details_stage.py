from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.model import (
    MAX_PIXELS_PER_SEMANTIC_DETAIL_V1,
    MAX_SEMANTIC_DETAILS_V1,
    PALETTE_LIGHT_STAGE_ID_V1,
    PALETTE_LIGHT_STAGE_SCHEMA_V1,
    PIXEL_PROGRAM_SCHEMA_V1,
    SEMANTIC_DETAILS_STAGE_ID_V1,
    SEMANTIC_DETAILS_STAGE_SCHEMA_V1,
    PaletteLightStageV1,
    SemanticDetailsStageV1,
    SemanticDetailsStageValidationError,
    validate_semantic_details_stage,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "semantic-details-stage.v1.schema.json"
)


def _valid_palette_stage() -> PaletteLightStageV1:
    return {
        "schema": PALETTE_LIGHT_STAGE_SCHEMA_V1,
        "stage": PALETTE_LIGHT_STAGE_ID_V1,
        "palette": [
            {"role": "body_base", "rgba": [88, 96, 120, 255]},
            {"role": "body_highlight", "rgba": [152, 160, 184, 255]},
            {"role": "accent", "rgba": [220, 88, 64, 255]},
            {"role": "cutout", "rgba": [0, 0, 0, 0]},
        ],
        "ramps": [
            {
                "id": "body",
                "colors": ["body_base", "body_highlight"],
            }
        ],
        "program": {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 16, "height": 16},
            "operations": [],
        },
    }


def _valid_stage() -> SemanticDetailsStageV1:
    return {
        "schema": SEMANTIC_DETAILS_STAGE_SCHEMA_V1,
        "stage": SEMANTIC_DETAILS_STAGE_ID_V1,
        "details": [
            {"id": "bottle_glint"},
            {"id": "seal_mark"},
        ],
        "program": {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 16, "height": 16},
            "operations": [
                {
                    "op": "set_pixels",
                    "pixels": [
                        [6, 5, 152, 160, 184, 255],
                        [7, 5, 152, 160, 184, 255],
                    ],
                },
                {
                    "op": "set_pixels",
                    "pixels": [[8, 9, 220, 88, 64, 255]],
                },
            ],
        },
    }


class SemanticDetailsStageTests(unittest.TestCase):
    def test_schema_is_versioned_closed_bounded_and_reuses_pixel_program(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            SEMANTIC_DETAILS_STAGE_SCHEMA_V1,
            "tracepixel.semantic-details-stage.v1",
        )
        self.assertEqual(SEMANTIC_DETAILS_STAGE_ID_V1, "semantic_details")
        self.assertEqual(MAX_SEMANTIC_DETAILS_V1, 64)
        self.assertEqual(MAX_PIXELS_PER_SEMANTIC_DETAIL_V1, 64)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:semantic-details-stage:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["required"],
            ["schema", "stage", "details", "program"],
        )
        self.assertEqual(
            schema["properties"]["details"]["maxItems"],
            MAX_SEMANTIC_DETAILS_V1,
        )
        self.assertEqual(
            schema["properties"]["program"]["$ref"],
            "pixel-program.v1.schema.json",
        )
        self.assertEqual(
            schema["$defs"]["semanticDetail"]["required"],
            ["id"],
        )
        self.assertEqual(json.loads(json.dumps(_valid_stage())), _valid_stage())

    def test_valid_stage_is_returned_without_copy_or_normalization(self) -> None:
        stage = _valid_stage()

        validated = validate_semantic_details_stage(
            stage,
            palette_light_stage=_valid_palette_stage(),
        )

        self.assertIs(validated, stage)
        self.assertIs(validated["details"], stage["details"])
        self.assertIs(validated["program"], stage["program"])

    def test_empty_semantic_details_stage_is_valid(self) -> None:
        stage = _valid_stage()
        stage["details"] = []
        stage["program"]["operations"] = []

        self.assertIs(
            validate_semantic_details_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            ),
            stage,
        )

    def test_detail_ids_are_bounded_unique_author_defined_locators(self) -> None:
        stage = _valid_stage()
        stage["details"][0]["id"] = "antenna_rune"
        self.assertIs(
            validate_semantic_details_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            ),
            stage,
        )

        duplicate = _valid_stage()
        duplicate["details"][1]["id"] = "bottle_glint"
        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                duplicate,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "duplicate_semantic_detail_id")
        self.assertEqual(caught.exception.path, "$.details[1].id")

        invalid = _valid_stage()
        invalid["details"][0]["id"] = "Eye"
        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                invalid,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "invalid_semantic_detail_id")
        self.assertEqual(caught.exception.path, "$.details[0].id")

    def test_detail_count_is_bounded_and_maps_one_to_one_to_operations(self) -> None:
        mismatch = _valid_stage()
        mismatch["details"] = mismatch["details"][:1]
        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                mismatch,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "detail_operation_mismatch")
        self.assertEqual(caught.exception.path, "$.details")

        oversized = _valid_stage()
        oversized["details"] = [
            {"id": f"detail_{index}"}
            for index in range(MAX_SEMANTIC_DETAILS_V1 + 1)
        ]
        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                oversized,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "too_many_semantic_details")
        self.assertEqual(caught.exception.path, "$.details")

    def test_each_detail_patch_must_be_non_empty_and_bounded(self) -> None:
        empty = _valid_stage()
        empty["program"]["operations"][0]["pixels"] = []
        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                empty,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "empty_semantic_detail")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels")

        oversized = _valid_stage()
        oversized["program"]["operations"][0]["pixels"] = [
            [6, 5, 152, 160, 184, 255]
            for _ in range(MAX_PIXELS_PER_SEMANTIC_DETAIL_V1 + 1)
        ]
        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                oversized,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "too_many_semantic_detail_pixels")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels")

    def test_detail_colors_must_come_from_the_declared_s3_palette(self) -> None:
        stage = _valid_stage()
        stage["program"]["operations"][0]["pixels"][0][2:6] = [1, 2, 3, 255]

        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            )

        self.assertEqual(caught.exception.code, "undeclared_palette_color")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[0]")

    def test_palette_declared_transparent_color_is_not_silently_forbidden(self) -> None:
        stage = _valid_stage()
        stage["program"]["operations"][1]["pixels"][0][2:6] = [0, 0, 0, 0]

        self.assertIs(
            validate_semantic_details_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            ),
            stage,
        )

    def test_context_and_stage_program_must_share_canvas(self) -> None:
        stage = _valid_stage()
        stage["program"]["canvas"] = {"width": 8, "height": 8}
        stage["program"]["operations"] = []
        stage["details"] = []

        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            )

        self.assertEqual(caught.exception.code, "canvas_mismatch")
        self.assertEqual(caught.exception.path, "$.program.canvas")

    def test_nested_context_and_program_failures_are_rebased(self) -> None:
        palette_stage = _valid_palette_stage()
        palette_stage["schema"] = "tracepixel.palette-light-stage.v0"  # type: ignore[typeddict-item]
        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                _valid_stage(),
                palette_light_stage=palette_stage,
            )
        self.assertEqual(caught.exception.code, "invalid_palette_light_stage")
        self.assertEqual(caught.exception.path, "$context.palette_light_stage.schema")

        stage = _valid_stage()
        stage["program"]["operations"][0]["pixels"][0][0] = 16
        with self.assertRaises(SemanticDetailsStageValidationError) as caught:
            validate_semantic_details_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "invalid_program")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[0]")

    def test_contract_fails_closed_without_pulling_later_stage_fields_forward(self) -> None:
        for extra_field, value in (
            ("outline", []),
            ("cleanup", []),
            ("input_stage", "shading"),
            ("preview", None),
        ):
            with self.subTest(extra_field=extra_field):
                stage = deepcopy(_valid_stage())
                stage[extra_field] = value
                with self.assertRaises(SemanticDetailsStageValidationError) as caught:
                    validate_semantic_details_stage(
                        stage,
                        palette_light_stage=_valid_palette_stage(),
                    )
                self.assertEqual(caught.exception.code, "invalid_fields")
                self.assertEqual(caught.exception.path, "$")


if __name__ == "__main__":
    unittest.main()
