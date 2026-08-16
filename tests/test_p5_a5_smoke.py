from __future__ import annotations

import unittest

from evidence.p5_a5.smoke import _SmokeQa
from tracepixel.raster import Canvas


class P5A5SmokeQaTests(unittest.TestCase):
    def test_empty_canvas_reports_only_deterministic_initial_failures(self) -> None:
        findings = _SmokeQa().evaluate(Canvas(16, 16))

        self.assertEqual(
            findings["findings"],
            [
                {
                    "rule": "structural.non_empty",
                    "category": "structural",
                    "severity": "error",
                },
                {
                    "rule": "connectivity.single_component",
                    "category": "connectivity",
                    "severity": "error",
                },
            ],
        )

    def test_minimal_connected_vertical_pair_passes_smoke_qa(self) -> None:
        canvas = Canvas(16, 16)
        canvas.set_pixel(7, 8, (200, 0, 0, 255))
        canvas.set_pixel(8, 8, (200, 0, 0, 255))

        findings = _SmokeQa().evaluate(canvas)

        self.assertEqual(findings["findings"], [])


if __name__ == "__main__":
    unittest.main()
