from __future__ import annotations

import unittest
from unittest.mock import patch

from tracepixel.qa import STRUCTURAL_QA_SCHEMA_V1, analyze_structural
from tracepixel.raster import Canvas


class StructuralQaTests(unittest.TestCase):
    def test_empty_canvas_reports_no_occupied_bounds_or_margins(self) -> None:
        canvas = Canvas(4, 3)

        facts = analyze_structural(canvas)

        self.assertEqual(facts["schema"], STRUCTURAL_QA_SCHEMA_V1)
        self.assertEqual(facts["dimensions"], {"width": 4, "height": 3})
        self.assertTrue(facts["empty"])
        self.assertEqual(facts["visible_pixels"], 0)
        self.assertIsNone(facts["occupied_bounds"])
        self.assertIsNone(facts["margins"])
        self.assertEqual(
            facts["edge_contact"],
            {"left": False, "top": False, "right": False, "bottom": False, "any": False},
        )
        self.assertEqual(
            facts["alpha"],
            {
                "transparent_pixels": 12,
                "translucent_pixels": 0,
                "opaque_pixels": 0,
                "has_translucency": False,
            },
        )

    def test_interior_occupancy_reports_exact_bounds_margins_and_alpha(self) -> None:
        canvas = Canvas(5, 4)
        canvas.set_pixels(
            [
                (1, 1, (10, 20, 30, 255)),
                (3, 2, (40, 50, 60, 128)),
                (2, 1, (99, 88, 77, 0)),
            ]
        )

        facts = analyze_structural(canvas)

        self.assertFalse(facts["empty"])
        self.assertEqual(facts["visible_pixels"], 2)
        self.assertEqual(facts["occupied_bounds"], {"x": 1, "y": 1, "width": 3, "height": 2})
        self.assertEqual(facts["margins"], {"left": 1, "top": 1, "right": 1, "bottom": 1})
        self.assertFalse(facts["edge_contact"]["any"])
        self.assertEqual(
            facts["alpha"],
            {
                "transparent_pixels": 18,
                "translucent_pixels": 1,
                "opaque_pixels": 1,
                "has_translucency": True,
            },
        )

    def test_edge_contact_is_reported_per_side(self) -> None:
        canvas = Canvas(3, 3)
        canvas.set_pixels(
            [
                (0, 1, (1, 1, 1, 255)),
                (1, 0, (1, 1, 1, 255)),
                (2, 1, (1, 1, 1, 255)),
                (1, 2, (1, 1, 1, 255)),
            ]
        )

        facts = analyze_structural(canvas)

        self.assertEqual(facts["occupied_bounds"], {"x": 0, "y": 0, "width": 3, "height": 3})
        self.assertEqual(facts["margins"], {"left": 0, "top": 0, "right": 0, "bottom": 0})
        self.assertEqual(
            facts["edge_contact"],
            {"left": True, "top": True, "right": True, "bottom": True, "any": True},
        )

    def test_transparent_rgb_does_not_make_a_pixel_visible(self) -> None:
        canvas = Canvas(2, 1)
        canvas.set_pixel(0, 0, (255, 12, 34, 0))

        facts = analyze_structural(canvas)

        self.assertTrue(facts["empty"])
        self.assertEqual(facts["alpha"]["transparent_pixels"], 2)

    def test_analysis_does_not_request_owned_rgba_snapshot(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(1, 1, (1, 2, 3, 255))

        with patch.object(Canvas, "rgba_bytes", side_effect=AssertionError("unexpected raster copy")):
            facts = analyze_structural(canvas)

        self.assertEqual(facts["visible_pixels"], 1)

    def test_analysis_is_deterministic_and_does_not_mutate_canvas(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(1, 0, (1, 2, 3, 64))
        before = canvas.rgba_bytes()

        first = analyze_structural(canvas)
        second = analyze_structural(canvas)

        self.assertEqual(first, second)
        self.assertEqual(canvas.rgba_bytes(), before)

    def test_non_canvas_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "tracepixel.raster.Canvas"):
            analyze_structural(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
