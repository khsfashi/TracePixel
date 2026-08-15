from __future__ import annotations

import json
from pathlib import Path
import unittest

from tracepixel.model import (
    PIXEL_PROGRAM_SCHEMA_V1,
    SET_PIXELS_OPERATION_V1,
    PixelProgramV1,
)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "pixel-program.v1.schema.json"


class PixelIrSchemaTests(unittest.TestCase):
    def test_schema_identity_is_explicitly_versioned(self) -> None:
        self.assertEqual(PIXEL_PROGRAM_SCHEMA_V1, "tracepixel.pixel-program.v1")
        self.assertEqual(SET_PIXELS_OPERATION_V1, "set_pixels")

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "urn:tracepixel:schema:pixel-program:v1")
        self.assertEqual(schema["properties"]["schema"]["const"], PIXEL_PROGRAM_SCHEMA_V1)
        self.assertEqual(
            schema["$defs"]["setPixelsOperation"]["properties"]["op"]["const"],
            SET_PIXELS_OPERATION_V1,
        )

    def test_schema_keeps_v1_surface_closed_and_bounded(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], ["schema", "canvas", "operations"])
        self.assertFalse(schema["$defs"]["canvas"]["additionalProperties"])
        self.assertFalse(schema["$defs"]["setPixelsOperation"]["additionalProperties"])
        self.assertEqual(schema["$defs"]["pixelEdit"]["minItems"], 6)
        self.assertEqual(schema["$defs"]["pixelEdit"]["maxItems"], 6)

    def test_minimal_program_is_plain_json_compatible_data(self) -> None:
        program: PixelProgramV1 = {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 2, "height": 1},
            "operations": [
                {
                    "op": SET_PIXELS_OPERATION_V1,
                    "pixels": [
                        [0, 0, 255, 0, 0, 255],
                        [1, 0, 0, 0, 0, 0],
                    ],
                }
            ],
        }

        encoded = json.dumps(program)
        decoded = json.loads(encoded)

        self.assertEqual(decoded, program)
        self.assertEqual(decoded["schema"], "tracepixel.pixel-program.v1")
        self.assertEqual(decoded["operations"][0]["pixels"][0], [0, 0, 255, 0, 0, 255])

    def test_operation_and_pixel_order_remain_explicit_arrays(self) -> None:
        program: PixelProgramV1 = {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 1, "height": 1},
            "operations": [
                {
                    "op": SET_PIXELS_OPERATION_V1,
                    "pixels": [
                        [0, 0, 1, 2, 3, 4],
                        [0, 0, 5, 6, 7, 8],
                    ],
                }
            ],
        }

        self.assertEqual(program["operations"][0]["pixels"][0][2:], [1, 2, 3, 4])
        self.assertEqual(program["operations"][0]["pixels"][1][2:], [5, 6, 7, 8])


if __name__ == "__main__":
    unittest.main()
