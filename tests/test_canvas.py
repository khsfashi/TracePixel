from __future__ import annotations

import unittest

from tracepixel.raster import (
    BatchEditError,
    Canvas,
    ColorValueError,
    PixelCoordinateError,
)


class CanvasTests(unittest.TestCase):
    def test_canvas_starts_as_transparent_black_rgba8(self) -> None:
        canvas = Canvas(3, 2)

        self.assertEqual(canvas.width, 3)
        self.assertEqual(canvas.height, 2)
        self.assertEqual(canvas.byte_length, 24)
        for y in range(canvas.height):
            for x in range(canvas.width):
                self.assertEqual(canvas.get_pixel(x, y), (0, 0, 0, 0))

    def test_set_and_get_preserve_exact_straight_alpha_bytes(self) -> None:
        canvas = Canvas(2, 2)

        canvas.set_pixel(1, 0, (255, 0, 0, 0))

        self.assertEqual(canvas.get_pixel(1, 0), (255, 0, 0, 0))
        self.assertEqual(canvas.get_pixel(0, 0), (0, 0, 0, 0))

    def test_single_pixel_failure_does_not_mutate_canvas(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(0, 0, (10, 20, 30, 40))

        with self.assertRaises(PixelCoordinateError):
            canvas.set_pixel(2, 0, (1, 2, 3, 4))
        with self.assertRaises(ColorValueError):
            canvas.set_pixel(0, 0, (1, 2, 3, 256))

        self.assertEqual(canvas.get_pixel(0, 0), (10, 20, 30, 40))

    def test_batch_applies_in_order_and_duplicate_coordinates_last_write_wins(self) -> None:
        canvas = Canvas(3, 2)

        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 4)),
                (2, 1, (5, 6, 7, 8)),
                (0, 0, (9, 10, 11, 12)),
            ]
        )

        self.assertEqual(canvas.get_pixel(0, 0), (9, 10, 11, 12))
        self.assertEqual(canvas.get_pixel(2, 1), (5, 6, 7, 8))
        self.assertEqual(canvas.get_pixel(1, 0), (0, 0, 0, 0))

    def test_invalid_batch_coordinate_causes_no_partial_mutation(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(1, 1, (20, 21, 22, 23))

        with self.assertRaises(PixelCoordinateError):
            canvas.set_pixels(
                [
                    (0, 0, (1, 2, 3, 4)),
                    (2, 0, (5, 6, 7, 8)),
                ]
            )

        self.assertEqual(canvas.get_pixel(0, 0), (0, 0, 0, 0))
        self.assertEqual(canvas.get_pixel(1, 1), (20, 21, 22, 23))

    def test_invalid_batch_color_causes_no_partial_mutation(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(1, 1, (20, 21, 22, 23))

        with self.assertRaises(ColorValueError):
            canvas.set_pixels(
                [
                    (0, 0, (1, 2, 3, 4)),
                    (1, 0, (5, 6, 7, 999)),
                ]
            )

        self.assertEqual(canvas.get_pixel(0, 0), (0, 0, 0, 0))
        self.assertEqual(canvas.get_pixel(1, 1), (20, 21, 22, 23))

    def test_malformed_batch_causes_no_partial_mutation(self) -> None:
        canvas = Canvas(2, 2)

        with self.assertRaises(BatchEditError):
            canvas.set_pixels(
                [
                    (0, 0, (1, 2, 3, 4)),
                    (1, 0),
                ]
            )

        self.assertEqual(canvas.get_pixel(0, 0), (0, 0, 0, 0))

    def test_empty_batch_is_valid_no_op(self) -> None:
        canvas = Canvas(1, 1)
        canvas.set_pixel(0, 0, (7, 8, 9, 10))

        canvas.set_pixels([])

        self.assertEqual(canvas.get_pixel(0, 0), (7, 8, 9, 10))


if __name__ == "__main__":
    unittest.main()
