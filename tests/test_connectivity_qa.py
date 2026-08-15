from __future__ import annotations

import unittest
from unittest.mock import patch

from tracepixel.qa import (
    CONNECTIVITY_NEIGHBORS_V1,
    CONNECTIVITY_QA_SCHEMA_V1,
    analyze_connectivity,
)
from tracepixel.raster import Canvas


class ConnectivityQaTests(unittest.TestCase):
    def test_empty_canvas_reports_no_components_or_isolated_pixels(self) -> None:
        canvas = Canvas(3, 2)

        result = analyze_connectivity(canvas)

        self.assertEqual(result["schema"], CONNECTIVITY_QA_SCHEMA_V1)
        self.assertEqual(result["connectivity"], CONNECTIVITY_NEIGHBORS_V1)
        self.assertEqual(result["connectivity"], 4)
        self.assertEqual(result["visible_pixels"], 0)
        self.assertEqual(result["components"], {"count": 0, "largest_pixels": 0})
        self.assertEqual(
            result["isolated_pixels"],
            {"count": 0, "has_isolated_pixels": False},
        )

    def test_edge_adjacency_connects_but_diagonal_contact_does_not(self) -> None:
        canvas = Canvas(3, 2)
        canvas.set_pixels(
            [
                (0, 0, (10, 20, 30, 255)),
                (1, 0, (10, 20, 30, 255)),
                (2, 1, (10, 20, 30, 255)),
            ]
        )

        result = analyze_connectivity(canvas)

        self.assertEqual(result["visible_pixels"], 3)
        self.assertEqual(result["components"], {"count": 2, "largest_pixels": 2})
        self.assertEqual(
            result["isolated_pixels"],
            {"count": 1, "has_isolated_pixels": True},
        )

    def test_translucent_pixels_are_visible_and_hidden_transparent_rgb_is_not(self) -> None:
        canvas = Canvas(3, 1)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 1)),
                (1, 0, (4, 5, 6, 128)),
                (2, 0, (255, 1, 2, 0)),
            ]
        )

        result = analyze_connectivity(canvas)

        self.assertEqual(result["visible_pixels"], 2)
        self.assertEqual(result["components"], {"count": 1, "largest_pixels": 2})
        self.assertEqual(
            result["isolated_pixels"],
            {"count": 0, "has_isolated_pixels": False},
        )

    def test_multiple_single_pixel_components_are_counted_exactly(self) -> None:
        canvas = Canvas(5, 1)
        canvas.set_pixels(
            [
                (0, 0, (1, 1, 1, 255)),
                (2, 0, (1, 1, 1, 255)),
                (4, 0, (1, 1, 1, 255)),
            ]
        )

        result = analyze_connectivity(canvas)

        self.assertEqual(result["components"], {"count": 3, "largest_pixels": 1})
        self.assertEqual(
            result["isolated_pixels"],
            {"count": 3, "has_isolated_pixels": True},
        )

    def test_long_component_is_iterative_and_not_limited_by_python_recursion_depth(self) -> None:
        width = 2048
        canvas = Canvas(width, 1)
        canvas.set_pixels(
            [(x, 0, (12, 34, 56, 255)) for x in range(width)]
        )

        result = analyze_connectivity(canvas)

        self.assertEqual(result["visible_pixels"], width)
        self.assertEqual(result["components"], {"count": 1, "largest_pixels": width})
        self.assertEqual(result["isolated_pixels"]["count"], 0)

    def test_analysis_does_not_request_owned_rgba_snapshot(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (0, 1, (4, 5, 6, 255)),
            ]
        )

        with patch.object(Canvas, "rgba_bytes", side_effect=AssertionError("unexpected raster copy")):
            result = analyze_connectivity(canvas)

        self.assertEqual(result["components"], {"count": 1, "largest_pixels": 2})

    def test_analysis_is_deterministic_and_does_not_mutate_canvas(self) -> None:
        canvas = Canvas(3, 3)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (1, 0, (4, 5, 6, 128)),
                (2, 2, (7, 8, 9, 255)),
            ]
        )
        before = canvas.rgba_bytes()

        first = analyze_connectivity(canvas)
        second = analyze_connectivity(canvas)

        self.assertEqual(first, second)
        self.assertEqual(canvas.rgba_bytes(), before)

    def test_non_canvas_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "tracepixel.raster.Canvas"):
            analyze_connectivity(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
