from __future__ import annotations

import json
import unittest
from pathlib import Path

from evidence.p4_q5.checkpoint import build_evidence, canonical_json


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence" / "p4_q5"


class P4Q5EvidenceTests(unittest.TestCase):
    def test_seeded_checkpoint_matches_committed_canonical_evidence(self) -> None:
        committed = (EVIDENCE_DIR / "structural.json").read_text(encoding="utf-8")
        generated = canonical_json(build_evidence())

        self.assertEqual(generated, committed)

    def test_checkpoint_covers_clean_and_seeded_failure_cases(self) -> None:
        evidence = json.loads((EVIDENCE_DIR / "structural.json").read_text(encoding="utf-8"))

        self.assertEqual(evidence["cases"]["clean"]["finding_count"], 0)
        seeded = evidence["cases"]["seeded_defects"]
        self.assertEqual(seeded["finding_count"], 9)
        self.assertEqual(
            {finding["category"] for finding in seeded["findings"]["findings"]},
            {"structural", "color", "connectivity", "shape", "tile"},
        )

    def test_preview_places_both_fixture_results_beside_findings_summary(self) -> None:
        preview = (EVIDENCE_DIR / "preview.svg").read_text(encoding="utf-8")

        self.assertIn("clean — 0 findings", preview)
        self.assertIn("seeded_defects — 9 findings", preview)
        self.assertIn("hidden RGB", preview)
        self.assertIn("Explanatory SVG only", preview)


if __name__ == "__main__":
    unittest.main()
