from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.model import (
    ART_INTENT_SCHEMA_V1,
    MAX_SHADING_APPLICATIONS_V1,
    PALETTE_LIGHT_STAGE_ID_V1,
    PALETTE_LIGHT_STAGE_SCHEMA_V1,
    PIXEL_PROGRAM_SCHEMA_V1,
    SHADING_STAGE_ID_V1,
    SHADING_STAGE_SCHEMA_V1,
    ArtIntentV1,
    PaletteLightStageV1,
    ShadingStageV1,
    ShadingStageValidationError,
    validate_shading_stage,
)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "shading-stage.v1.schema.json"


def _valid_art_intent() -> ArtIntentV1:
    return {
        "schema": ART_INTENT_SCHEMA_V1,
        "asset_class": "potion",
        "canvas": {"width": 16, "height": 16},
        "composition": {
            "occupied_bounds": {"x": 4, "y": 4, "width": 8, "height": 8},
            "facing": None,
            "symmetry": None,
            "light_direction": "top_left",
            "palette_budget": 4,
        },
    }


def _valid_palette_stage() -> PaletteLightStageV1:
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
            "operations": [],
        },
    }


def _valid_stage() -> ShadingStageV1:
    return {
        "schema": SHADING_STAGE_SCHEMA_V1,
        "stage": SHADING_STAGE_ID_V1,
        "applications": [
            {
                "id": "body_light",
                "ramp_id": "body",
                "source_role": "body_base",
                "target_role": "body_highlight",
                "relation": "toward_light",
            },
            {
                "id": "body_shadow",
                "ramp_id": "body",
                "source_role": "body_base",
                "target_role": "body_shadow",
                "relation": "away_from_light",
            },
        ],
        "program": {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 16, "height": 16},
            "operations": [
                {
                    "op": "set_pixels",
                    "pixels": [[5, 5, 152, 160, 184, 255]],
                },
                {
                    "op": "set_pixels",
                    "pixels": [[10, 10, 44, 48, 64, 255]],
                },
            ],
        },
    }


class ShadingStageTests(unittest.TestCase):
    def test_schema_is_versioned_closed_bounded_and_reuses_pixel_program(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(SHADING_STAGE_SCHEMA_V1, "tracepixel.shading-stage.v1")
        self.assertEqual(SHADING_STAGE_ID_V1, "shading")
        self.assertEqual(MAX_SHADING_APPLICATIONS_V1, 64)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:shading-stage:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["required"],
            ["schema", "stage", "applications", "program"],
        )
        self.assertEqual(
            schema["properties"]["applications"]["maxItems"],
            MAX_SHADING_APPLICATIONS_V1,
        )
        self.assertEqual(
            schema["properties"]["program"]["$ref"],
            "pixel-program.v1.schema.json",
        )
        self.assertEqual(json.loads(json.dumps(_valid_stage())), _valid_stage())

    def test_valid_stage_is_returned_without_copy_or_normalization(self) -> None:
        stage = _valid_stage()

        validated = validate_shading_stage(
            stage,
            art_intent=_valid_art_intent(),
            palette_light_stage=_valid_palette_stage(),
        )

        self.assertIs(validated, stage)
        self.assertIs(validated["applications"], stage["applications"])
        self.assertIs(validated["program"], stage["program"])

    def test_empty_stage_allows_intent_without_direction_or_bounds(self) -> None:
        intent = _valid_art_intent()
        intent["composition"]["light_direction"] = None
        intent["composition"]["occupied_bounds"] = None
        stage = _valid_stage()
        stage["applications"] = []
        stage["program"]["operations"] = []

        self.assertIs(
            validate_shading_stage(
                stage,
                art_intent=intent,
                palette_light_stage=_valid_palette_stage(),
            ),
            stage,
        )

    def test_non_empty_shading_requires_direction_and_occupied_bounds(self) -> None:
        intent = _valid_art_intent()
        intent["composition"]["light_direction"] = None
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                _valid_stage(),
                art_intent=intent,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "missing_light_direction")
        self.assertEqual(
            caught.exception.path,
            "$context.art_intent.composition.light_direction",
        )

        intent = _valid_art_intent()
        intent["composition"]["occupied_bounds"] = None
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                _valid_stage(),
                art_intent=intent,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "missing_occupied_bounds")
        self.assertEqual(
            caught.exception.path,
            "$context.art_intent.composition.occupied_bounds",
        )

    def test_contexts_and_stage_program_must_share_canvas(self) -> None:
        stage = _valid_stage()
        stage["program"]["canvas"] = {"width": 8, "height": 8}
        stage["program"]["operations"] = []
        stage["applications"] = []
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "canvas_mismatch")
        self.assertEqual(caught.exception.path, "$.program.canvas")

        palette_stage = _valid_palette_stage()
        palette_stage["program"]["canvas"] = {"width": 8, "height": 8}
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                _valid_stage(),
                art_intent=_valid_art_intent(),
                palette_light_stage=palette_stage,
            )
        self.assertEqual(caught.exception.code, "context_canvas_mismatch")
        self.assertEqual(
            caught.exception.path,
            "$context.palette_light_stage.program.canvas",
        )

    def test_application_count_is_bounded_and_maps_one_to_one_to_operations(self) -> None:
        stage = _valid_stage()
        stage["applications"] = stage["applications"][:1]
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "application_operation_mismatch")
        self.assertEqual(caught.exception.path, "$.applications")

        stage = _valid_stage()
        stage["applications"] = [
            {
                "id": f"shade_{index}",
                "ramp_id": "body",
                "source_role": "body_base",
                "target_role": "body_highlight",
                "relation": "toward_light",
            }
            for index in range(MAX_SHADING_APPLICATIONS_V1 + 1)
        ]
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "too_many_shading_applications")
        self.assertEqual(caught.exception.path, "$.applications")

    def test_application_ids_are_unique_and_references_must_resolve(self) -> None:
        stage = _valid_stage()
        stage["applications"][1]["id"] = "body_light"
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "duplicate_shading_application_id")
        self.assertEqual(caught.exception.path, "$.applications[1].id")

        stage = _valid_stage()
        stage["applications"][0]["ramp_id"] = "missing"
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "unknown_light_ramp")
        self.assertEqual(caught.exception.path, "$.applications[0].ramp_id")

        stage = _valid_stage()
        stage["applications"][0]["target_role"] = "accent"
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "target_role_not_in_ramp")
        self.assertEqual(caught.exception.path, "$.applications[0].target_role")

    def test_ramp_order_is_authored_light_level_truth_without_rgb_luminance_math(self) -> None:
        palette_stage = _valid_palette_stage()
        palette_stage["palette"][0]["rgba"] = [250, 250, 250, 255]
        palette_stage["palette"][1]["rgba"] = [10, 10, 10, 255]
        palette_stage["palette"][2]["rgba"] = [128, 0, 128, 255]
        stage = _valid_stage()
        stage["program"]["operations"][0]["pixels"][0][2:6] = [128, 0, 128, 255]
        stage["program"]["operations"][1]["pixels"][0][2:6] = [250, 250, 250, 255]

        self.assertIs(
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=palette_stage,
            ),
            stage,
        )

    def test_relation_must_move_in_the_declared_ramp_direction(self) -> None:
        stage = _valid_stage()
        stage["applications"][0]["target_role"] = "body_shadow"
        stage["program"]["operations"][0]["pixels"][0][2:6] = [44, 48, 64, 255]

        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )

        self.assertEqual(caught.exception.code, "invalid_ramp_transition")
        self.assertEqual(caught.exception.path, "$.applications[0].target_role")

    def test_shading_transition_preserves_alpha(self) -> None:
        palette_stage = _valid_palette_stage()
        palette_stage["palette"][2]["rgba"] = [152, 160, 184, 128]
        stage = _valid_stage()
        stage["program"]["operations"][0]["pixels"][0][2:6] = [152, 160, 184, 128]

        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=palette_stage,
            )

        self.assertEqual(caught.exception.code, "alpha_change")
        self.assertEqual(caught.exception.path, "$.applications[0].target_role")

    def test_operation_pixels_must_use_the_declared_target_role_color(self) -> None:
        stage = _valid_stage()
        stage["program"]["operations"][0]["pixels"][0][2] = 151

        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )

        self.assertEqual(caught.exception.code, "target_color_mismatch")
        self.assertEqual(
            caught.exception.path,
            "$.program.operations[0].pixels[0]",
        )

    def test_pixels_must_stay_in_bounds_and_on_the_declared_light_half_plane(self) -> None:
        outside = _valid_stage()
        outside["program"]["operations"][0]["pixels"][0][0:2] = [3, 3]
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                outside,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "outside_occupied_bounds")

        wrong_side = _valid_stage()
        wrong_side["program"]["operations"][0]["pixels"][0][0:2] = [10, 10]
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                wrong_side,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "wrong_light_side")
        self.assertEqual(
            caught.exception.path,
            "$.program.operations[0].pixels[0]",
        )

    def test_nested_context_and_program_failures_are_rebased(self) -> None:
        intent = _valid_art_intent()
        intent["composition"]["light_direction"] = "north"  # type: ignore[typeddict-item]
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                _valid_stage(),
                art_intent=intent,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "invalid_art_intent")
        self.assertEqual(
            caught.exception.path,
            "$context.art_intent.composition.light_direction",
        )

        palette_stage = _valid_palette_stage()
        palette_stage["palette"][1]["role"] = "body_shadow"
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                _valid_stage(),
                art_intent=_valid_art_intent(),
                palette_light_stage=palette_stage,
            )
        self.assertEqual(caught.exception.code, "invalid_palette_light_stage")
        self.assertEqual(
            caught.exception.path,
            "$context.palette_light_stage.palette[1].role",
        )

        stage = _valid_stage()
        stage["program"]["operations"][0]["pixels"][0][0] = 16
        with self.assertRaises(ShadingStageValidationError) as caught:
            validate_shading_stage(
                stage,
                art_intent=_valid_art_intent(),
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "invalid_program")
        self.assertEqual(
            caught.exception.path,
            "$.program.operations[0].pixels[0]",
        )

    def test_contract_fails_closed_without_pulling_later_stage_fields_forward(self) -> None:
        for extra_field, value in (
            ("details", []),
            ("outline", []),
            ("preview", None),
        ):
            with self.subTest(extra_field=extra_field):
                stage = deepcopy(_valid_stage())
                stage[extra_field] = value
                with self.assertRaises(ShadingStageValidationError) as caught:
                    validate_shading_stage(
                        stage,
                        art_intent=_valid_art_intent(),
                        palette_light_stage=_valid_palette_stage(),
                    )
                self.assertEqual(caught.exception.code, "invalid_fields")
                self.assertEqual(caught.exception.path, "$")


if __name__ == "__main__":
    unittest.main()
