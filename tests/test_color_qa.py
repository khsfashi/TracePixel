from __future__ import annotations

import unittest
from unittest.mock import patch

from tracepixel.qa import COLOR_QA_SCHEMA_V1, ColorQaConfigurationError, analyze_color
from tracepixel.raster import Canvas


class ColorQaTests(unittest.TestCase):
    def test_empty_canvas_reports_zero_visible_colors_without_implicit_policy(self) -> None:
        canvas = Canvas(3, 2)

        result = analyze_color(canvas)

        self.assertEqual(result["schema"], COLOR_QA_SCHEMA_V1)
        self.assertEqual(result["colors"], {"visible_rgba_colors": 0})
        self.assertEqual(
            result["transparent_rgb"],
            {"nonzero_rgb_pixels": 0, "has_nonzero_rgb": False},
        )
        self.assertIsNone(result["palette_membership"])
        self.assertIsNone(result["maximum_colors"])
        self.assertIsNone(result["transparent_rgb_policy"])

    def test_visible_color_count_is_exact_rgba8_and_ignores_hidden_transparent_rgb(self) -> None:
        canvas = Canvas(4, 2)
        canvas.set_pixels(
            [
                (0, 0, (10, 20, 30, 255)),
                (1, 0, (10, 20, 30, 255)),
                (2, 0, (10, 20, 30, 128)),
                (3, 0, (40, 50, 60, 255)),
                (0, 1, (99, 88, 77, 0)),
            ]
        )

        result = analyze_color(canvas)

        self.assertEqual(result["colors"]["visible_rgba_colors"], 3)
        self.assertEqual(result["transparent_rgb"]["nonzero_rgb_pixels"], 1)
        self.assertTrue(result["transparent_rgb"]["has_nonzero_rgb"])

    def test_palette_membership_counts_visible_pixels_and_distinct_nonmembers(self) -> None:
        canvas = Canvas(4, 1)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (1, 0, (1, 2, 3, 255)),
                (2, 0, (4, 5, 6, 255)),
                (3, 0, (9, 9, 9, 0)),
            ]
        )

        result = analyze_color(canvas, palette=[(1, 2, 3, 255), (7, 8, 9, 255)])

        self.assertEqual(
            result["palette_membership"],
            {
                "palette_size": 2,
                "visible_pixels": 3,
                "matching_visible_pixels": 2,
                "nonmatching_visible_pixels": 1,
                "nonmatching_visible_colors": 1,
                "satisfied": False,
            },
        )

    def test_empty_explicit_palette_accepts_only_an_empty_visible_raster(self) -> None:
        empty = Canvas(1, 1)
        nonempty = Canvas(1, 1)
        nonempty.set_pixel(0, 0, (1, 2, 3, 255))

        self.assertTrue(analyze_color(empty, palette=[])["palette_membership"]["satisfied"])
        self.assertFalse(analyze_color(nonempty, palette=[])["palette_membership"]["satisfied"])

    def test_maximum_color_check_is_only_applied_when_requested(self) -> None:
        canvas = Canvas(3, 1)
        canvas.set_pixels(
            [
                (0, 0, (1, 1, 1, 255)),
                (1, 0, (2, 2, 2, 255)),
                (2, 0, (1, 1, 1, 255)),
            ]
        )

        passing = analyze_color(canvas, max_colors=2)
        failing = analyze_color(canvas, max_colors=1)

        self.assertEqual(
            passing["maximum_colors"],
            {"limit": 2, "actual_visible_colors": 2, "satisfied": True},
        )
        self.assertEqual(
            failing["maximum_colors"],
            {"limit": 1, "actual_visible_colors": 2, "satisfied": False},
        )

    def test_transparent_rgb_policy_distinguishes_allow_and_require_zero(self) -> None:
        canvas = Canvas(2, 1)
        canvas.set_pixel(0, 0, (12, 0, 34, 0))

        allowed = analyze_color(canvas, transparent_rgb_policy="allow")
        required_zero = analyze_color(canvas, transparent_rgb_policy="require_zero")

        self.assertEqual(
            allowed["transparent_rgb_policy"],
            {"policy": "allow", "nonzero_rgb_pixels": 1, "satisfied": True},
        )
        self.assertEqual(
            required_zero["transparent_rgb_policy"],
            {"policy": "require_zero", "nonzero_rgb_pixels": 1, "satisfied": False},
        )

    def test_policy_configuration_is_validated_before_scan(self) -> None:
        canvas = Canvas(1, 1)

        with self.assertRaisesRegex(ColorQaConfigurationError, "duplicates"):
            analyze_color(canvas, palette=[(1, 2, 3, 255), (1, 2, 3, 255)])
        with self.assertRaisesRegex(ColorQaConfigurationError, "palette\[0\]"):
            analyze_color(canvas, palette=[(1, 2, 3, True)])
        with self.assertRaisesRegex(ColorQaConfigurationError, "at most 256"):
            analyze_color(canvas, palette=[(0, 0, 0, 0)] * 257)
        with self.assertRaisesRegex(ColorQaConfigurationError, "max_colors"):
            analyze_color(canvas, max_colors=0)
        with self.assertRaisesRegex(ColorQaConfigurationError, "transparent_rgb_policy"):
            analyze_color(canvas, transparent_rgb_policy="forbid")

    def test_analysis_does_not_request_owned_rgba_snapshot(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixel(1, 1, (1, 2, 3, 255))

        with patch.object(Canvas, "rgba_bytes", side_effect=AssertionError("unexpected raster copy")):
            result = analyze_color(canvas, palette=[(1, 2, 3, 255)], max_colors=1)

        self.assertTrue(result["palette_membership"]["satisfied"])
        self.assertTrue(result["maximum_colors"]["satisfied"])

    def test_analysis_is_deterministic_and_does_not_mutate_canvas(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 255)),
                (1, 0, (4, 5, 6, 255)),
                (0, 1, (7, 8, 9, 0)),
            ]
        )
        before = canvas.rgba_bytes()
        kwargs = {
            "palette": [(1, 2, 3, 255), (4, 5, 6, 255)],
            "max_colors": 2,
            "transparent_rgb_policy": "require_zero",
        }

        first = analyze_color(canvas, **kwargs)
        second = analyze_color(canvas, **kwargs)

        self.assertEqual(first, second)
        self.assertEqual(canvas.rgba_bytes(), before)

    def test_non_canvas_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "tracepixel.raster.Canvas"):
            analyze_color(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
