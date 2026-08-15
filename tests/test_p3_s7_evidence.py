from __future__ import annotations

from pathlib import Path
import unittest

from evidence.p3_s7.fixture import PREVIEW_SCALE, build_evidence

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "evidence" / "p3_s7"


class P3S7EvidenceTests(unittest.TestCase):
    def test_complete_staged_fixture_matches_committed_raster_evidence_exactly(self) -> None:
        result, manifest = build_evidence()

        self.assertEqual(
            result.canvas.rgba_bytes(),
            (EVIDENCE_DIR / "final.rgba").read_bytes(),
        )
        self.assertEqual(PREVIEW_SCALE, 2)
        self.assertEqual(len(result.previews), 6)

        output_previews = manifest["outputs"]["previews"]
        self.assertEqual(len(output_previews), len(result.previews))
        for snapshot, output in zip(result.previews, output_previews, strict=True):
            self.assertEqual(snapshot.stage, output["stage"])
            self.assertEqual(snapshot.metadata.png_sha256, output["png_sha256"])
            self.assertEqual(
                snapshot.png,
                (EVIDENCE_DIR / output["file"]).read_bytes(),
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
