from __future__ import annotations

import json
import unittest
from pathlib import Path

from evidence.p1_r3.potion import build_evidence, render_fixture

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "evidence" / "p1_r3"


class P1R3ReplayFixtureTests(unittest.TestCase):
    def test_replay_matches_committed_authoritative_rgba_exactly(self) -> None:
        self.assertEqual(
            render_fixture().rgba_bytes(),
            (EVIDENCE_DIR / "potion.rgba").read_bytes(),
        )

    def test_structural_metadata_is_stable_and_matches_manifest(self) -> None:
        first = build_evidence()[3]
        second = build_evidence()[3]
        committed = json.loads(
            (EVIDENCE_DIR / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(first, second)
        self.assertEqual(first, committed)

    def test_native_and_preview_png_match_committed_evidence(self) -> None:
        _, native_png, preview_png, manifest = build_evidence()

        self.assertEqual(native_png, (EVIDENCE_DIR / "potion.png").read_bytes())
        self.assertEqual(preview_png, (EVIDENCE_DIR / "potion@8x.png").read_bytes())
        self.assertEqual(manifest["outputs"]["native"]["kind"], "native")
        self.assertEqual(
            manifest["outputs"]["preview"]["kind"],
            "nearest-preview",
        )
        self.assertEqual(manifest["outputs"]["preview"]["scale"], 8)
        self.assertEqual(
            (
                manifest["outputs"]["preview"]["width"],
                manifest["outputs"]["preview"]["height"],
            ),
            (128, 128),
        )


if __name__ == "__main__":
    unittest.main()
