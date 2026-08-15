from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.model import (
    MAX_OUTLINE_CLEANUP_ACTIONS_V1,
    MAX_PIXELS_PER_OUTLINE_CLEANUP_ACTION_V1,
    OUTLINE_CLEANUP_STAGE_ID_V1,
    OUTLINE_CLEANUP_STAGE_SCHEMA_V1,
    PALETTE_LIGHT_STAGE_ID_V1,
    PALETTE_LIGHT_STAGE_SCHEMA_V1,
    PIXEL_PROGRAM_SCHEMA_V1,
    OutlineCleanupStageV1,
    OutlineCleanupStageValidationError,
    PaletteLightStageV1,
    validate_outline_cleanup_stage,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "outline-cleanup-stage.v1.schema.json"
)


def _valid_palette_stage() -> PaletteLightStageV1:
    return {
        "schema": PALETTE_LIGHT_STAGE_SCHEMA_V1,
        "stage": PALETTE_LIGHT_STAGE_ID_V1,
        "palette": [
            {"role": "body_base", "rgba": [88, 96, 120, 255]},
            {"role": "outline_dark", "rgba": [32, 36, 48, 255]},
            {"role": "accent", "rgba": [220, 88, 64, 255]},
            {"role": "cutout", "rgba": [0, 0, 0, 0]},
        ],
        "ramps": [],
        "program": {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 16, "height": 16},
            "operations": [],
        },
    }


def _valid_stage() -> OutlineCleanupStageV1:
    return {
        "schema": OUTLINE_CLEANUP_STAGE_SCHEMA_V1,
        "stage": OUTLINE_CLEANUP_STAGE_ID_V1,
        "actions": [
            {"id": "outer_edge", "kind": "outline"},
            {"id": "stray_corner", "kind": "cleanup"},
        ],
        "program": {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 16, "height": 16},
            "operations": [
                {
                    "op": "set_pixels",
                    "pixels": [
                        [4, 7, 32, 36, 48, 255],
                        [4, 8, 32, 36, 48, 255],
                    ],
                },
                {
                    "op": "set_pixels",
                    "pixels": [[12, 11, 0, 0, 0, 0]],
                },
            ],
        },
    }


class OutlineCleanupStageTests(unittest.TestCase):
    def test_schema_is_versioned_closed_bounded_and_reuses_pixel_program(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            OUTLINE_CLEANUP_STAGE_SCHEMA_V1,
            "tracepixel.outline-cleanup-stage.v1",
        )
        self.assertEqual(OUTLINE_CLEANUP_STAGE_ID_V1, "outline_cleanup")
        self.assertEqual(MAX_OUTLINE_CLEANUP_ACTIONS_V1, 64)
        self.assertEqual(MAX_PIXELS_PER_OUTLINE_CLEANUP_ACTION_V1, 64)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:outline-cleanup-stage:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["required"],
            ["schema", "stage", "actions", "program"],
        )
        self.assertEqual(
            schema["properties"]["actions"]["maxItems"],
            MAX_OUTLINE_CLEANUP_ACTIONS_V1,
        )
        self.assertEqual(
            schema["properties"]["program"]["$ref"],
            "pixel-program.v1.schema.json",
        )
        self.assertEqual(
            schema["$defs"]["outlineCleanupAction"]["required"],
            ["id", "kind"],
        )
        self.assertEqual(
            schema["$defs"]["outlineCleanupAction"]["properties"]["kind"]["enum"],
            ["outline", "cleanup"],
        )
        self.assertEqual(json.loads(json.dumps(_valid_stage())), _valid_stage())

    def test_valid_stage_is_returned_without_copy_or_normalization(self) -> None:
        stage = _valid_stage()

        validated = validate_outline_cleanup_stage(
            stage,
            palette_light_stage=_valid_palette_stage(),
        )

        self.assertIs(validated, stage)
        self.assertIs(validated["actions"], stage["actions"])
        self.assertIs(validated["program"], stage["program"])

    def test_empty_outline_cleanup_stage_is_valid(self) -> None:
        stage = _valid_stage()
        stage["actions"] = []
        stage["program"]["operations"] = []

        self.assertIs(
            validate_outline_cleanup_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            ),
            stage,
        )

    def test_action_kinds_are_explicit_authored_classification_only(self) -> None:
        stage = _valid_stage()
        stage["actions"][0]["kind"] = "cleanup"
        stage["actions"][1]["kind"] = "outline"
        self.assertIs(
            validate_outline_cleanup_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            ),
            stage,
        )

        invalid = _valid_stage()
        invalid["actions"][0]["kind"] = "smooth"  # type: ignore[typeddict-item]
        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                invalid,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "invalid_outline_cleanup_kind")
        self.assertEqual(caught.exception.path, "$.actions[0].kind")

    def test_action_ids_are_bounded_unique_author_defined_locators(self) -> None:
        stage = _valid_stage()
        stage["actions"][0]["id"] = "left_edge_pass"
        self.assertIs(
            validate_outline_cleanup_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            ),
            stage,
        )

        duplicate = _valid_stage()
        duplicate["actions"][1]["id"] = "outer_edge"
        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                duplicate,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "duplicate_outline_cleanup_action_id")
        self.assertEqual(caught.exception.path, "$.actions[1].id")

        invalid = _valid_stage()
        invalid["actions"][0]["id"] = "Edge"
        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                invalid,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "invalid_outline_cleanup_action_id")
        self.assertEqual(caught.exception.path, "$.actions[0].id")

    def test_action_count_is_bounded_and_maps_one_to_one_to_operations(self) -> None:
        mismatch = _valid_stage()
        mismatch["actions"] = mismatch["actions"][:1]
        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                mismatch,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "action_operation_mismatch")
        self.assertEqual(caught.exception.path, "$.actions")

        oversized = _valid_stage()
        oversized["actions"] = [
            {"id": f"action_{index}", "kind": "cleanup"}
            for index in range(MAX_OUTLINE_CLEANUP_ACTIONS_V1 + 1)
        ]
        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                oversized,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "too_many_outline_cleanup_actions")
        self.assertEqual(caught.exception.path, "$.actions")

    def test_each_action_patch_must_be_non_empty_and_bounded(self) -> None:
        empty = _valid_stage()
        empty["program"]["operations"][0]["pixels"] = []
        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                empty,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "empty_outline_cleanup_action")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels")

        oversized = _valid_stage()
        oversized["program"]["operations"][0]["pixels"] = [
            [4, 7, 32, 36, 48, 255]
            for _ in range(MAX_PIXELS_PER_OUTLINE_CLEANUP_ACTION_V1 + 1)
        ]
        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                oversized,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "too_many_outline_cleanup_pixels")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels")

    def test_action_colors_must_come_from_the_declared_s3_palette(self) -> None:
        stage = _valid_stage()
        stage["program"]["operations"][0]["pixels"][0][2:6] = [1, 2, 3, 255]

        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            )

        self.assertEqual(caught.exception.code, "undeclared_palette_color")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[0]")

    def test_palette_declared_transparent_color_can_be_used_for_cleanup(self) -> None:
        stage = _valid_stage()
        stage["program"]["operations"][1]["pixels"][0][2:6] = [0, 0, 0, 0]

        self.assertIs(
            validate_outline_cleanup_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            ),
            stage,
        )

    def test_context_and_stage_program_must_share_canvas(self) -> None:
        stage = _valid_stage()
        stage["program"]["canvas"] = {"width": 8, "height": 8}
        stage["program"]["operations"] = []
        stage["actions"] = []

        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            )

        self.assertEqual(caught.exception.code, "canvas_mismatch")
        self.assertEqual(caught.exception.path, "$.program.canvas")

    def test_nested_context_and_program_failures_are_rebased(self) -> None:
        palette_stage = _valid_palette_stage()
        palette_stage["schema"] = "tracepixel.palette-light-stage.v0"  # type: ignore[typeddict-item]
        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                _valid_stage(),
                palette_light_stage=palette_stage,
            )
        self.assertEqual(caught.exception.code, "invalid_palette_light_stage")
        self.assertEqual(caught.exception.path, "$context.palette_light_stage.schema")

        stage = _valid_stage()
        stage["program"]["operations"][0]["pixels"][0][0] = 16
        with self.assertRaises(OutlineCleanupStageValidationError) as caught:
            validate_outline_cleanup_stage(
                stage,
                palette_light_stage=_valid_palette_stage(),
            )
        self.assertEqual(caught.exception.code, "invalid_program")
        self.assertEqual(caught.exception.path, "$.program.operations[0].pixels[0]")

    def test_contract_fails_closed_without_encoding_subjective_or_s7_fields(self) -> None:
        for extra_field, value in (
            ("outline_thickness", 1),
            ("smoothness", "high"),
            ("input_stage", "semantic_details"),
            ("preview", None),
        ):
            with self.subTest(extra_field=extra_field):
                stage = deepcopy(_valid_stage())
                stage[extra_field] = value
                with self.assertRaises(OutlineCleanupStageValidationError) as caught:
                    validate_outline_cleanup_stage(
                        stage,
                        palette_light_stage=_valid_palette_stage(),
                    )
                self.assertEqual(caught.exception.code, "invalid_fields")
                self.assertEqual(caught.exception.path, "$")


if __name__ == "__main__":
    unittest.main()
