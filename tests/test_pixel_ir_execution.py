from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from tracepixel.model import (
    PIXEL_PROGRAM_SCHEMA_V1,
    PixelProgramCanvasMismatchError,
    PixelProgramValidationError,
    apply_pixel_program,
    execute_pixel_program,
)
from tracepixel.raster import Canvas


def executable_program() -> dict[str, object]:
    return {
        "schema": PIXEL_PROGRAM_SCHEMA_V1,
        "canvas": {"width": 2, "height": 2},
        "operations": [
            {
                "op": "set_pixels",
                "pixels": [
                    [0, 0, 1, 2, 3, 4],
                    [1, 0, 9, 8, 7, 6],
                    [0, 0, 5, 6, 7, 8],
                ],
            },
            {
                "op": "set_pixels",
                "pixels": [
                    [1, 1, 20, 21, 22, 23],
                    [1, 0, 10, 11, 12, 13],
                ],
            },
        ],
    }


class PixelIrExecutionTests(unittest.TestCase):
    def test_executes_operations_and_duplicates_in_serialized_order(self) -> None:
        program = executable_program()
        before = deepcopy(program)

        canvas = execute_pixel_program(program)

        self.assertEqual((canvas.width, canvas.height), (2, 2))
        self.assertEqual(canvas.get_pixel(0, 0), (5, 6, 7, 8))
        self.assertEqual(canvas.get_pixel(1, 0), (10, 11, 12, 13))
        self.assertEqual(canvas.get_pixel(0, 1), (0, 0, 0, 0))
        self.assertEqual(canvas.get_pixel(1, 1), (20, 21, 22, 23))
        self.assertEqual(program, before)

    def test_replay_is_provider_free_and_returns_independent_authority(self) -> None:
        program = executable_program()

        first = execute_pixel_program(program)
        second = execute_pixel_program(program)

        self.assertIsNot(first, second)
        self.assertEqual(first.rgba_bytes(), second.rgba_bytes())

        first.set_pixel(0, 0, (99, 98, 97, 96))
        self.assertEqual(second.get_pixel(0, 0), (5, 6, 7, 8))

    def test_empty_program_produces_fresh_transparent_canvas(self) -> None:
        program: dict[str, object] = {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 1, "height": 2},
            "operations": [],
        }

        canvas = execute_pixel_program(program)

        self.assertEqual(canvas.rgba_bytes(), bytes(8))

    def test_full_program_is_validated_before_canvas_construction(self) -> None:
        program = executable_program()
        program["operations"][1]["pixels"][0][2] = 256  # type: ignore[index]

        with patch("tracepixel.model.execution.Canvas") as canvas_type:
            with self.assertRaises(PixelProgramValidationError) as caught:
                execute_pixel_program(program)

        self.assertEqual(caught.exception.code, "invalid_color")
        self.assertEqual(caught.exception.path, "$.operations[1].pixels[0]")
        canvas_type.assert_not_called()

    def test_applies_validated_program_to_existing_canvas_without_replacing_authority(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(0, 1, (90, 91, 92, 93))

        returned = apply_pixel_program(canvas, executable_program())

        self.assertIs(returned, canvas)
        self.assertEqual(canvas.get_pixel(0, 0), (5, 6, 7, 8))
        self.assertEqual(canvas.get_pixel(1, 0), (10, 11, 12, 13))
        self.assertEqual(canvas.get_pixel(0, 1), (90, 91, 92, 93))
        self.assertEqual(canvas.get_pixel(1, 1), (20, 21, 22, 23))

    def test_existing_canvas_application_rejects_dimension_mismatch_before_mutation(self) -> None:
        canvas = Canvas(1, 1)
        before = canvas.rgba_bytes()

        with self.assertRaises(PixelProgramCanvasMismatchError):
            apply_pixel_program(canvas, executable_program())

        self.assertEqual(canvas.rgba_bytes(), before)


if __name__ == "__main__":
    unittest.main()
