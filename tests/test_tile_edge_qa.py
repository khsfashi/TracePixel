from __future__ import annotations

import unittest
from unittest.mock import patch

from tracepixel.qa import (
    TILE_EDGE_QA_SCHEMA_V1,
    TileEdgeQaConfigurationError,
    analyze_tile_edges,
)
from tracepixel.raster import Canvas


class TileEdgeQaTests(unittest.TestCase):
    def test_empty_canvas_has_exact_matching_edges_and_corners(self) -> None:
        canvas = Canvas(3, 2)

        result = analyze_tile_edges(canvas)

        self.assertEqual(result["schema"], TILE_EDGE_QA_SCHEMA_V1)
        self.assertEqual(
            result["left_right"],
            {"compared_positions": 2, "mismatched_positions": 0, "matches": True},
        )
        self.assertEqual(
            result["top_bottom"],
            {"compared_positions": 3, "mismatched_positions": 0, "matches": True},
        )
        self.assertEqual(
            result["corners"],
            {"all_equal": True, "distinct_rgba_colors": 1},
        )
        self.assertIsNone(result["contract"])

    def test_left_right_reports_exact_mismatch_count(self) -> None:
        canvas = Canvas(4, 3)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (3, 0, (1, 2, 3, 255)),
                (0, 1, (4, 5, 6, 255)),
                (3, 1, (9, 9, 9, 255)),
                (0, 2, (7, 8, 9, 128)),
                (3, 2, (7, 8, 9, 64)),
            ]
        )

        result = analyze_tile_edges(canvas)

        self.assertEqual(
            result["left_right"],
            {"compared_positions": 3, "mismatched_positions": 2, "matches": False},
        )

    def test_top_bottom_reports_exact_mismatch_count(self) -> None:
        canvas = Canvas(3, 4)
        canvas.set_pixels(
            [
                (0, 0, (1, 1, 1, 255)),
                (0, 3, (1, 1, 1, 255)),
                (1, 0, (2, 2, 2, 255)),
                (1, 3, (3, 3, 3, 255)),
                (2, 0, (4, 4, 4, 255)),
                (2, 3, (4, 4, 4, 255)),
            ]
        )

        result = analyze_tile_edges(canvas)

        self.assertEqual(
            result["top_bottom"],
            {"compared_positions": 3, "mismatched_positions": 1, "matches": False},
        )

    def test_exact_equality_includes_hidden_transparent_rgb(self) -> None:
        canvas = Canvas(2, 1)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 0)),
                (1, 0, (9, 2, 3, 0)),
            ]
        )

        result = analyze_tile_edges(canvas)

        self.assertFalse(result["left_right"]["matches"])
        self.assertEqual(result["left_right"]["mismatched_positions"], 1)

    def test_single_column_and_row_compare_each_boundary_position_to_itself(self) -> None:
        canvas = Canvas(1, 1)
        canvas.set_pixel(0, 0, (9, 8, 7, 6))

        result = analyze_tile_edges(canvas)

        self.assertEqual(result["left_right"]["compared_positions"], 1)
        self.assertTrue(result["left_right"]["matches"])
        self.assertEqual(result["top_bottom"]["compared_positions"], 1)
        self.assertTrue(result["top_bottom"]["matches"])
        self.assertTrue(result["corners"]["all_equal"])

    def test_required_edge_contract_is_only_emitted_when_requested(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixels(
            [
                (0, 0, (1, 1, 1, 255)),
                (1, 0, (1, 1, 1, 255)),
                (0, 1, (2, 2, 2, 255)),
                (1, 1, (2, 2, 2, 255)),
            ]
        )

        horizontal = analyze_tile_edges(canvas, required_edges="left_right")
        both = analyze_tile_edges(canvas, required_edges="both")

        self.assertEqual(
            horizontal["contract"],
            {
                "required_edges": "left_right",
                "require_equal_corners": False,
                "satisfied": True,
            },
        )
        self.assertEqual(
            both["contract"],
            {
                "required_edges": "both",
                "require_equal_corners": False,
                "satisfied": False,
            },
        )

    def test_corner_only_contract_uses_all_four_authoritative_corner_values(self) -> None:
        canvas = Canvas(3, 3)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (2, 0, (1, 2, 3, 255)),
                (0, 2, (1, 2, 3, 255)),
                (2, 2, (4, 5, 6, 255)),
            ]
        )

        result = analyze_tile_edges(canvas, require_equal_corners=True)

        self.assertEqual(
            result["corners"],
            {"all_equal": False, "distinct_rgba_colors": 2},
        )
        self.assertEqual(
            result["contract"],
            {
                "required_edges": None,
                "require_equal_corners": True,
                "satisfied": False,
            },
        )

    def test_invalid_configuration_is_rejected_before_raster_access(self) -> None:
        canvas = Canvas(2, 2)

        with patch.object(
            Canvas,
            "_rgba_view",
            side_effect=AssertionError("raster access should not begin"),
        ):
            with self.assertRaisesRegex(TileEdgeQaConfigurationError, "required_edges"):
                analyze_tile_edges(canvas, required_edges="diagonal")
            with self.assertRaisesRegex(
                TileEdgeQaConfigurationError, "require_equal_corners"
            ):
                analyze_tile_edges(canvas, require_equal_corners=1)

    def test_analysis_does_not_request_owned_rgba_snapshot(self) -> None:
        canvas = Canvas(3, 2)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (2, 0, (1, 2, 3, 255)),
            ]
        )

        with patch.object(Canvas, "rgba_bytes", side_effect=AssertionError("unexpected copy")):
            result = analyze_tile_edges(canvas, required_edges="left_right")

        self.assertTrue(result["left_right"]["matches"])

    def test_analysis_is_deterministic_and_does_not_mutate_canvas(self) -> None:
        canvas = Canvas(4, 3)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (3, 0, (1, 2, 3, 255)),
                (0, 2, (4, 5, 6, 128)),
                (3, 2, (7, 8, 9, 128)),
            ]
        )
        before = canvas.rgba_bytes()

        first = analyze_tile_edges(
            canvas,
            required_edges="both",
            require_equal_corners=True,
        )
        second = analyze_tile_edges(
            canvas,
            required_edges="both",
            require_equal_corners=True,
        )

        self.assertEqual(first, second)
        self.assertEqual(canvas.rgba_bytes(), before)

    def test_non_canvas_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "tracepixel.raster.Canvas"):
            analyze_tile_edges(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
