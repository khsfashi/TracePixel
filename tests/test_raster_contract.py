from __future__ import annotations

import unittest

from tracepixel.raster import (
    BYTES_PER_PIXEL,
    MAX_CANVAS_BYTES,
    MAX_CANVAS_DIMENSION,
    CanvasSizeError,
    CanvasSpec,
    ColorValueError,
    PixelCoordinateError,
    validate_rgba8,
)


class RasterContractTests(unittest.TestCase):
    def test_canvas_layout_is_row_major_rgba8(self) -> None:
        spec = CanvasSpec(3, 2)

        self.assertEqual(BYTES_PER_PIXEL, 4)
        self.assertEqual(spec.row_stride, 12)
        self.assertEqual(spec.byte_length, 24)
        self.assertEqual(spec.offset(0, 0), 0)
        self.assertEqual(spec.offset(2, 0), 8)
        self.assertEqual(spec.offset(0, 1), 12)
        self.assertEqual(spec.offset(2, 1), 20)

    def test_coordinates_are_zero_based_half_open(self) -> None:
        spec = CanvasSpec(2, 3)

        self.assertTrue(spec.contains(0, 0))
        self.assertTrue(spec.contains(1, 2))
        self.assertFalse(spec.contains(-1, 0))
        self.assertFalse(spec.contains(2, 0))
        self.assertFalse(spec.contains(0, 3))

        for coordinate in [(-1, 0), (2, 0), (0, -1), (0, 3)]:
            with self.subTest(coordinate=coordinate):
                with self.assertRaises(PixelCoordinateError):
                    spec.offset(*coordinate)

    def test_bool_and_non_integer_coordinates_are_rejected(self) -> None:
        spec = CanvasSpec(2, 2)

        for coordinate in [(True, 0), (0, False), (1.0, 0), (0, "1")]:
            with self.subTest(coordinate=coordinate):
                with self.assertRaises(PixelCoordinateError):
                    spec.offset(*coordinate)

    def test_canvas_dimensions_are_bounded_before_allocation(self) -> None:
        maximum = CanvasSpec(MAX_CANVAS_DIMENSION, MAX_CANVAS_DIMENSION)
        self.assertEqual(maximum.byte_length, MAX_CANVAS_BYTES)

        invalid_dimensions = [
            (0, 1),
            (1, 0),
            (-1, 1),
            (1, -1),
            (True, 1),
            (1, False),
            (1.0, 1),
            (1, "1"),
            (MAX_CANVAS_DIMENSION + 1, 1),
            (1, MAX_CANVAS_DIMENSION + 1),
        ]
        for dimensions in invalid_dimensions:
            with self.subTest(dimensions=dimensions):
                with self.assertRaises(CanvasSizeError):
                    CanvasSpec(*dimensions)

    def test_rgba8_requires_four_exact_integer_channels(self) -> None:
        valid_colors = [
            (0, 0, 0, 0),
            (255, 255, 255, 255),
            [12, 34, 56, 78],
        ]
        for color in valid_colors:
            with self.subTest(color=color):
                validate_rgba8(color)

        invalid_colors = [
            (0, 0, 0),
            (0, 0, 0, 0, 0),
            (-1, 0, 0, 0),
            (256, 0, 0, 0),
            (True, 0, 0, 0),
            (1.0, 0, 0, 0),
            "0000",
            bytes((0, 0, 0, 0)),
        ]
        for color in invalid_colors:
            with self.subTest(color=color):
                with self.assertRaises(ColorValueError):
                    validate_rgba8(color)


if __name__ == "__main__":
    unittest.main()
