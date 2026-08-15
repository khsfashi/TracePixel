from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.model import (
    MAX_LIGHT_RAMPS_V1,
    MAX_PALETTE_COLORS_V1,
    PALETTE_LIGHT_STAGE_ID_V1,
    PALETTE_LIGHT_STAGE_SCHEMA_V1,
    PIXEL_PROGRAM_SCHEMA_V1,
    PaletteLightStageV1,
    PaletteLightStageValidationError,
    validate_palette_light_stage,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "palette-light-stage.v1.schema.json"
)


def _valid_stage() -> PaletteLightStageV1:
    return {
        "schema": PALETTE_LIGHT_STAGE_SCHEMA_V1,
        "stage": PALETTE_LIGHT_STAGE_ID_V1,
        "palette": [
            {"role": "body_shadow", "rgba": [44, 48, 64, 255]},
            {"role": "body_base", "rgba": [88, 96, 120, 255]},
            {"role": "body_highlight", "rgba": [152, 160, 184, 255]},
            {"role": "accent", "rgba": [220, 88, 64, 255]},
        ],
        "ramps": [
            {
                "id": "body",
                "colors": ["body_shadow", "body_base", "body_highlight"],
            }
        ],
        "program": {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 16, "height": 16},
            "operations": [
                {
                    "op": "set_pixels",
                    "pixels": [
                        [7, 5, 88, 96, 120, 255],
                        [8, 5, 152, 160, 184, 255],
                        [6, 6, 44, 48, 64, 255],
                        [9, 6, 220, 88, 64, 255],
                    ],
                }
            ],
        },
    }


class PaletteLightStageSchemaTests(unittest.TestCase):
    def test_schema_is_versioned_closed_bounded_and_reuses_pixel_program_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            PALETTE_LIGHT_STAGE_SCHEMA_V1,
            "tracepixel.palette-light-stage.v1",
        )
        self.assertEqual(PALETTE_LIGHT_STAGE_ID_V1, "palette_light_ramp")
        self.assertEqual(MAX_PALETTE_COLORS_V1, 256)
        self.assertEqual(MAX_LIGHT_RAMPS_V1, 32)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:palette-light-stage:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["required"],
            ["schema", "stage", "palette", "ramps", "program"],
        )
        self.assertEqual(
            schema["properties"]["palette"]["maxItems"],
            MAX_PALETTE_COLORS_V1,
        )
        self.assertEqual(
            schema["properties"]["ramps"]["maxItems"],
            MAX_LIGHT_RAMPS_V1,
        )
        self.assertEqual(
            schema["properties"]["program"]["$ref"],
            "pixel-program.v1.schema.json",
        )
        self.assertEqual(json.loads(json.dumps(_valid_stage())), _valid_stage())

    def test_valid_stage_is_returned_without_copy_or_normalization(self) -> None:
        stage = _valid_stage()

        validated = validate_palette_light_stage(stage)

        self.assertIs(validated, stage)
        self.assertIs(validated["palette"], stage["palette"])
        self.assertIs(validated["ramps"], stage["ramps"])
        self.assertIs(validated["program"], stage["program"])

    def test_palette_roles_and_exact_colors_are_unique_and_bounded(self) -> None:
        duplicate_role = deepcopy(_valid_stage())
        duplicate_role["palette"][1]["role"] = "body_shadow"
        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(duplicate_role)
        self.assertEqual(caught.exception.code, "duplicate_palette_role")
        self.assertEqual(caught.exception.path, "$.palette[1].role")

        duplicate_color = deepcopy(_valid_stage())
        duplicate_color["palette"][1]["rgba"] = [44, 48, 64, 255]
        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(duplicate_color)
        self.assertEqual(caught.exception.code, "duplicate_palette_color")
        self.assertEqual(caught.exception.path, "$.palette[1].rgba")

        invalid_role = deepcopy(_valid_stage())
        invalid_role["palette"][0]["role"] = "Body Shadow"
        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(invalid_role)
        self.assertEqual(caught.exception.code, "invalid_palette_role")
        self.assertEqual(caught.exception.path, "$.palette[0].role")

        too_many = deepcopy(_valid_stage())
        too_many["palette"] = [
            {
                "role": f"c{index}",
                "rgba": [index & 0xFF, (index >> 8) & 0xFF, 0, 255],
            }
            for index in range(MAX_PALETTE_COLORS_V1 + 1)
        ]
        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(too_many)
        self.assertEqual(caught.exception.code, "too_many_palette_colors")
        self.assertEqual(caught.exception.path, "$.palette")

    def test_palette_color_reuses_exact_rgba8_contract(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["palette"][0]["rgba"] = [44, 48, 64, 256]

        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(stage)

        self.assertEqual(caught.exception.code, "invalid_palette_color")
        self.assertEqual(caught.exception.path, "$.palette[0].rgba")

    def test_ramps_are_optional_and_empty_program_is_not_forced_to_rewrite_pixels(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["ramps"] = []
        stage["program"]["operations"] = []

        self.assertIs(validate_palette_light_stage(stage), stage)

    def test_light_ramps_require_known_distinct_roles_and_unique_ids(self) -> None:
        unknown = deepcopy(_valid_stage())
        unknown["ramps"][0]["colors"][1] = "missing"
        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(unknown)
        self.assertEqual(caught.exception.code, "unknown_palette_role")
        self.assertEqual(caught.exception.path, "$.ramps[0].colors[1]")

        repeated = deepcopy(_valid_stage())
        repeated["ramps"][0]["colors"][1] = "body_shadow"
        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(repeated)
        self.assertEqual(caught.exception.code, "duplicate_light_ramp_role")
        self.assertEqual(caught.exception.path, "$.ramps[0].colors[1]")

        duplicate_id = deepcopy(_valid_stage())
        duplicate_id["ramps"].append(
            {"id": "body", "colors": ["body_base", "accent"]}
        )
        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(duplicate_id)
        self.assertEqual(caught.exception.code, "duplicate_light_ramp_id")
        self.assertEqual(caught.exception.path, "$.ramps[1].id")

        too_many = deepcopy(_valid_stage())
        too_many["ramps"] = [
            {"id": f"r{index}", "colors": ["body_shadow", "body_base"]}
            for index in range(MAX_LIGHT_RAMPS_V1 + 1)
        ]
        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(too_many)
        self.assertEqual(caught.exception.code, "too_many_light_ramps")
        self.assertEqual(caught.exception.path, "$.ramps")

    def test_ramp_order_is_authored_and_not_numeric_luminance_truth(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["palette"][0]["rgba"] = [250, 250, 250, 255]
        stage["palette"][1]["rgba"] = [10, 10, 10, 255]
        stage["palette"][2]["rgba"] = [128, 0, 128, 255]
        stage["program"]["operations"][0]["pixels"] = [
            [7, 5, 250, 250, 250, 255],
            [8, 5, 10, 10, 10, 255],
            [9, 5, 128, 0, 128, 255],
        ]

        self.assertIs(validate_palette_light_stage(stage), stage)

    def test_stage_local_program_cannot_introduce_undeclared_color(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["program"]["operations"][0]["pixels"][0][2] = 89

        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(stage)

        self.assertEqual(caught.exception.code, "undeclared_palette_color")
        self.assertEqual(
            caught.exception.path,
            "$.program.operations[0].pixels[0]",
        )

    def test_nested_pixel_program_failure_is_rebased_under_program_path(self) -> None:
        stage = deepcopy(_valid_stage())
        stage["program"]["operations"][0]["pixels"][0][0] = 16

        with self.assertRaises(PaletteLightStageValidationError) as caught:
            validate_palette_light_stage(stage)

        self.assertEqual(caught.exception.code, "invalid_program")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[0]")
        self.assertIn("invalid_coordinate", caught.exception.message)

    def test_contract_fails_closed_and_does_not_duplicate_later_stage_or_intent_fields(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            frozenset(schema["properties"]),
            {"schema", "stage", "palette", "ramps", "program"},
        )

        for extra_field, value in (
            ("palette_budget", 8),
            ("light_direction", "top_left"),
            ("shading", []),
        ):
            with self.subTest(extra_field=extra_field):
                stage = deepcopy(_valid_stage())
                stage[extra_field] = value
                with self.assertRaises(PaletteLightStageValidationError) as caught:
                    validate_palette_light_stage(stage)
                self.assertEqual(caught.exception.code, "invalid_fields")
                self.assertEqual(caught.exception.path, "$")


if __name__ == "__main__":
    unittest.main()
