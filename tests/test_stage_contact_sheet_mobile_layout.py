from __future__ import annotations

import unittest

from evidence.p6_v1.checkpoint import build_reference_sheet


class StageContactSheetMobileLayoutTests(unittest.TestCase):
    def test_reference_sheet_uses_phone_readable_fixed_stage_cells(self) -> None:
        sheet = build_reference_sheet()
        layout = sheet.manifest["layout"]
        assert isinstance(layout, dict)
        self.assertGreaterEqual(layout["cell_width"], layout["minimum_cell_width"])
        self.assertGreaterEqual(layout["minimum_cell_width"], 112)
        self.assertGreaterEqual(layout["label_height"], 30)
        self.assertGreaterEqual(layout["label_font_size"], 10)
        self.assertLessEqual(layout["width"], 400)
        self.assertEqual(layout["source_image_scaling"], "none")

        svg = sheet.svg.decode("utf-8")
        for label in (
            "silhouette",
            "major forms",
            "palette light ramp",
            "shading",
            "semantic details",
            "outline cleanup",
        ):
            self.assertIn(f">{label}</text>", svg)
        self.assertNotIn(">01 silhouette</text>", svg)
        self.assertNotIn(">06 outline cleanup</text>", svg)


if __name__ == "__main__":
    unittest.main()
