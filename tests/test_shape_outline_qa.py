from __future__ import annotations

import unittest
from unittest.mock import patch

from tracepixel.qa import (
    SHAPE_OUTLINE_QA_SCHEMA_V1,
    ShapeQaConfigurationError,
    analyze_shape_outline,
)
from tracepixel.raster import Canvas


class ShapeOutlineQaTests(unittest.TestCase):
    def test_empty_canvas_reports_zero_outline_facts_and_no_implicit_symmetry(self) -> None:
        canvas = Canvas(3, 2)

        result = analyze_shape_outline(canvas)

        self.assertEqual(result["schema"], SHAPE_OUTLINE_QA_SCHEMA_V1)
        self.assertEqual(result["visible_pixels"], 0)
        self.assertIsNone(result["symmetry"])
        self.assertEqual(
            result["outline"],
            {
                "boundary_pixels": 0,
                "interior_pixels": 0,
                "visible_adjacencies": {
                    "horizontal": 0,
                    "vertical": 0,
                    "total": 0,
                },
                "exposed_edges": {
                    "top": 0,
                    "right": 0,
                    "bottom": 0,
                    "left": 0,
                    "total": 0,
                },
            },
        )

    def test_full_three_by_three_block_has_exact_perimeter_and_one_interior_pixel(self) -> None:
        canvas = Canvas(3, 3)
        canvas.set_pixels(
            [
                (x, y, (10 + x, 20 + y, 30, 255))
                for y in range(3)
                for x in range(3)
            ]
        )

        result = analyze_shape_outline(canvas)

        self.assertEqual(result["visible_pixels"], 9)
        self.assertEqual(result["outline"]["boundary_pixels"], 8)
        self.assertEqual(result["outline"]["interior_pixels"], 1)
        self.assertEqual(
            result["outline"]["visible_adjacencies"],
            {"horizontal": 6, "vertical": 6, "total": 12},
        )
        self.assertEqual(
            result["outline"]["exposed_edges"],
            {"top": 3, "right": 3, "bottom": 3, "left": 3, "total": 12},
        )

    def test_outline_identity_matches_four_v_minus_twice_adjacencies(self) -> None:
        canvas = Canvas(4, 3)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (1, 0, (1, 2, 3, 255)),
                (1, 1, (1, 2, 3, 255)),
                (2, 1, (1, 2, 3, 255)),
                (3, 2, (1, 2, 3, 255)),
            ]
        )

        result = analyze_shape_outline(canvas)
        adjacencies = result["outline"]["visible_adjacencies"]["total"]
        perimeter = result["outline"]["exposed_edges"]["total"]

        self.assertEqual(perimeter, 4 * result["visible_pixels"] - 2 * adjacencies)
        self.assertEqual(
            result["outline"]["visible_adjacencies"],
            {"horizontal": 2, "vertical": 1, "total": 3},
        )
        self.assertEqual(perimeter, 14)

    def test_vertical_symmetry_compares_visibility_not_rgba_color(self) -> None:
        canvas = Canvas(5, 3)
        canvas.set_pixels(
            [
                (0, 0, (255, 0, 0, 1)),
                (4, 0, (0, 255, 0, 255)),
                (1, 1, (10, 20, 30, 255)),
                (3, 1, (200, 100, 50, 128)),
                (2, 2, (1, 2, 3, 255)),
            ]
        )

        result = analyze_shape_outline(canvas, required_symmetry="vertical")

        self.assertEqual(
            result["symmetry"],
            {
                "requested": "vertical",
                "vertical": {"matches": True, "mismatched_pairs": 0},
                "horizontal": None,
            },
        )

    def test_both_symmetry_axes_report_mismatches_independently(self) -> None:
        canvas = Canvas(3, 3)
        canvas.set_pixels(
            [
                (0, 0, (1, 1, 1, 255)),
                (2, 0, (2, 2, 2, 255)),
            ]
        )

        result = analyze_shape_outline(canvas, required_symmetry="both")

        self.assertEqual(
            result["symmetry"],
            {
                "requested": "both",
                "vertical": {"matches": True, "mismatched_pairs": 0},
                "horizontal": {"matches": False, "mismatched_pairs": 2},
            },
        )

    def test_hidden_transparent_rgb_is_not_shape_and_translucent_pixel_is_shape(self) -> None:
        canvas = Canvas(2, 1)
        canvas.set_pixels(
            [
                (0, 0, (255, 1, 2, 0)),
                (1, 0, (3, 4, 5, 1)),
            ]
        )

        result = analyze_shape_outline(canvas)

        self.assertEqual(result["visible_pixels"], 1)
        self.assertEqual(result["outline"]["boundary_pixels"], 1)
        self.assertEqual(result["outline"]["interior_pixels"], 0)
        self.assertEqual(result["outline"]["exposed_edges"]["total"], 4)

    def test_asymmetric_shape_is_not_checked_when_symmetry_is_not_requested(self) -> None:
        canvas = Canvas(4, 1)
        canvas.set_pixel(0, 0, (1, 2, 3, 255))

        result = analyze_shape_outline(canvas)

        self.assertIsNone(result["symmetry"])

    def test_invalid_required_symmetry_is_rejected_before_scan(self) -> None:
        canvas = Canvas(1, 1)

        with patch.object(
            Canvas,
            "_rgba_view",
            side_effect=AssertionError("scan should not begin"),
        ):
            with self.assertRaisesRegex(ShapeQaConfigurationError, "required_symmetry"):
                analyze_shape_outline(
                    canvas,
                    required_symmetry="diagonal",  # type: ignore[arg-type]
                )

    def test_analysis_does_not_request_owned_rgba_snapshot(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (1, 0, (4, 5, 6, 255)),
            ]
        )

        with patch.object(Canvas, "rgba_bytes", side_effect=AssertionError("unexpected copy")):
            result = analyze_shape_outline(canvas, required_symmetry="vertical")

        self.assertEqual(result["visible_pixels"], 2)

    def test_analysis_is_deterministic_and_does_not_mutate_canvas(self) -> None:
        canvas = Canvas(3, 2)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (2, 0, (4, 5, 6, 128)),
                (1, 1, (7, 8, 9, 255)),
            ]
        )
        before = canvas.rgba_bytes()

        first = analyze_shape_outline(canvas, required_symmetry="both")
        second = analyze_shape_outline(canvas, required_symmetry="both")

        self.assertEqual(first, second)
        self.assertEqual(canvas.rgba_bytes(), before)

    def test_non_canvas_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "tracepixel.raster.Canvas"):
            analyze_shape_outline(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
