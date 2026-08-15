from __future__ import annotations

from pathlib import Path
import unittest

from evidence.p3_s7.fixture import PREVIEW_SCALE, build_evidence

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "evidence" / "p3_s7"
EXPECTED_PREVIEW_SHA256 = (
    "69ac9cae43cc01f714c4e1aa27961493474186c3d80aad5a6ceb4c45dfafde78",
    "f181d2b4cb1e5e538e1d0d16ebf872fcf7221c63e09865ea9f6ecfdcd8a61104",
    "f19177fe422cd9dc6d2a97e4f57317f246712bb1b23a1081da93e3cf0b741bbc",
    "4f9f1f4e75aa67c7321fc75a291270798654ecb247f759aa24a7f0d4498d2b23",
    "729c6dba1ab4ee3ad155039e7146a2d483b6a12ac1f13ad0318158d7aff7963d",
    "cfcf56ee3c1051614d8620dd4edf7501b3eb4d08652cabdb7b667135b477dbf8",
)


class P3S7EvidenceTests(unittest.TestCase):
    def test_complete_staged_fixture_matches_committed_and_frozen_evidence(self) -> None:
        result, manifest = build_evidence()

        self.assertEqual(
            result.canvas.rgba_bytes(),
            (EVIDENCE_DIR / "final.rgba").read_bytes(),
        )
        self.assertEqual(PREVIEW_SCALE, 2)
        self.assertEqual(len(result.previews), 6)

        output_previews = manifest["outputs"]["previews"]
        self.assertEqual(len(output_previews), len(result.previews))
        for snapshot, output, expected_digest in zip(
            result.previews,
            output_previews,
            EXPECTED_PREVIEW_SHA256,
            strict=True,
        ):
            self.assertEqual(snapshot.stage, output["stage"])
            self.assertEqual(snapshot.metadata.png_sha256, output["png_sha256"])
            self.assertEqual(snapshot.metadata.png_sha256, expected_digest)
            self.assertEqual((snapshot.metadata.width, snapshot.metadata.height), (32, 32))

        preview_svg = (EVIDENCE_DIR / "stage-preview.svg").read_text(encoding="utf-8")
        for index, snapshot in enumerate(result.previews, start=1):
            self.assertIn(
                f'id="{index:02d}-{snapshot.stage.replace("_", "-")}"',
                preview_svg,
            )

    def test_fixture_records_full_applied_path_and_repair_locality(self) -> None:
        _, manifest = build_evidence()
        records = manifest["pipeline"]["stages"]

        self.assertEqual([record["status"] for record in records], ["applied"] * 6)
        self.assertEqual(records[0]["input_stage"], "art_intent")
        self.assertTrue(all(record["program_sha256"] for record in records))
        self.assertTrue(all(record["preview"] is not None for record in records))
        self.assertEqual(
            records[-1]["touched_bounds"],
            {"x": 4, "y": 7, "width": 8, "height": 2},
        )


if __name__ == "__main__":
    unittest.main()
