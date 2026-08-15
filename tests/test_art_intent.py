from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import unittest

from tracepixel.model import (
    ART_INTENT_SCHEMA_V1,
    ArtIntentV1,
    ArtIntentValidationError,
    validate_art_intent,
)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "art-intent.v1.schema.json"


def _valid_intent() -> ArtIntentV1:
    return {
        "schema": ART_INTENT_SCHEMA_V1,
        "asset_class": "potion",
        "canvas": {"width": 16, "height": 16},
        "composition": {
            "occupied_bounds": {"x": 2, "y": 1, "width": 12, "height": 14},
            "facing": None,
            "symmetry": {"axis": "vertical", "strength": "hint"},
            "light_direction": "top_left",
            "palette_budget": 8,
        },
    }


class ArtIntentSchemaTests(unittest.TestCase):
    def test_schema_is_versioned_closed_and_json_compatible(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(ART_INTENT_SCHEMA_V1, "tracepixel.art-intent.v1")
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:art-intent:v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["required"],
            ["schema", "asset_class", "canvas", "composition"],
        )
        self.assertFalse(schema["$defs"]["composition"]["additionalProperties"])
        self.assertEqual(json.loads(json.dumps(_valid_intent())), _valid_intent())

    def test_valid_intent_is_returned_without_copy_or_normalization(self) -> None:
        intent = _valid_intent()
        validated = validate_art_intent(intent)

        self.assertIs(validated, intent)
        self.assertEqual(validated["asset_class"], "potion")
        self.assertEqual(validated["composition"]["light_direction"], "top_left")

    def test_nullable_composition_fields_are_explicitly_supported(self) -> None:
        intent = _valid_intent()
        intent["composition"] = {
            "occupied_bounds": None,
            "facing": None,
            "symmetry": None,
            "light_direction": None,
            "palette_budget": None,
        }

        self.assertIs(validate_art_intent(intent), intent)

    def test_canvas_uses_existing_p1_dimension_contract(self) -> None:
        for invalid_width in (0, 4097, True):
            with self.subTest(invalid_width=invalid_width):
                intent = deepcopy(_valid_intent())
                intent["canvas"]["width"] = invalid_width  # type: ignore[typeddict-item]
                with self.assertRaises(ArtIntentValidationError) as caught:
                    validate_art_intent(intent)
                self.assertEqual(caught.exception.code, "invalid_canvas")
                self.assertEqual(caught.exception.path, "$.canvas")

    def test_occupied_bounds_must_fit_inside_canvas(self) -> None:
        intent = deepcopy(_valid_intent())
        intent["composition"]["occupied_bounds"] = {
            "x": 8,
            "y": 1,
            "width": 9,
            "height": 14,
        }

        with self.assertRaises(ArtIntentValidationError) as caught:
            validate_art_intent(intent)

        self.assertEqual(caught.exception.code, "invalid_bounds")
        self.assertEqual(caught.exception.path, "$.composition.occupied_bounds")

    def test_composition_enums_are_bounded(self) -> None:
        cases = (
            ("facing", "diagonal", "$.composition.facing"),
            ("light_direction", "front", "$.composition.light_direction"),
        )
        for field, value, path in cases:
            with self.subTest(field=field):
                intent = deepcopy(_valid_intent())
                intent["composition"][field] = value  # type: ignore[literal-required]
                with self.assertRaises(ArtIntentValidationError) as caught:
                    validate_art_intent(intent)
                self.assertEqual(caught.exception.code, "invalid_value")
                self.assertEqual(caught.exception.path, path)

    def test_symmetry_is_explicit_hint_or_requirement(self) -> None:
        intent = deepcopy(_valid_intent())
        intent["composition"]["symmetry"] = {
            "axis": "vertical",
            "strength": "optional",
        }

        with self.assertRaises(ArtIntentValidationError) as caught:
            validate_art_intent(intent)

        self.assertEqual(caught.exception.code, "invalid_value")
        self.assertEqual(caught.exception.path, "$.composition.symmetry.strength")

    def test_palette_budget_is_optional_but_bounded_when_present(self) -> None:
        for invalid_budget in (0, 257, True):
            with self.subTest(invalid_budget=invalid_budget):
                intent = deepcopy(_valid_intent())
                intent["composition"]["palette_budget"] = invalid_budget  # type: ignore[typeddict-item]
                with self.assertRaises(ArtIntentValidationError) as caught:
                    validate_art_intent(intent)
                self.assertEqual(caught.exception.code, "invalid_palette_budget")
                self.assertEqual(caught.exception.path, "$.composition.palette_budget")

    def test_missing_or_extra_fields_fail_closed(self) -> None:
        missing = deepcopy(_valid_intent())
        del missing["composition"]["facing"]
        with self.assertRaises(ArtIntentValidationError) as caught:
            validate_art_intent(missing)
        self.assertEqual(caught.exception.code, "invalid_fields")
        self.assertEqual(caught.exception.path, "$.composition")

        extra = deepcopy(_valid_intent())
        extra["style"] = "cute"
        with self.assertRaises(ArtIntentValidationError) as caught:
            validate_art_intent(extra)
        self.assertEqual(caught.exception.code, "invalid_fields")
        self.assertEqual(caught.exception.path, "$")

    def test_subjective_style_and_stage_fields_are_not_part_of_s0_contract(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        root_fields = frozenset(schema["properties"])
        composition_fields = frozenset(schema["$defs"]["composition"]["properties"])

        self.assertNotIn("style", root_fields)
        self.assertNotIn("recognizability", root_fields)
        self.assertNotIn("stages", root_fields)
        self.assertNotIn("silhouette", composition_fields)
        self.assertNotIn("forms", composition_fields)


if __name__ == "__main__":
    unittest.main()
