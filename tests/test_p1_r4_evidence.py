from __future__ import annotations

import json
import unittest
from pathlib import Path

from evidence.p1_r4.benchmark import (
    REPORT_SCHEMA,
    STRUCTURAL_SCHEMA,
    build_runtime_report,
    build_structural_evidence,
)

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "evidence" / "p1_r4"


class P1R4EvidenceTests(unittest.TestCase):
    def test_structural_byte_evidence_matches_committed_golden(self) -> None:
        committed = json.loads(
            (EVIDENCE_DIR / "structural.json").read_text(encoding="utf-8")
        )
        generated = build_structural_evidence()

        self.assertEqual(generated["schema"], STRUCTURAL_SCHEMA)
        self.assertEqual(generated, committed)

    def test_structural_cases_preserve_copy_and_preview_contracts(self) -> None:
        evidence = build_structural_evidence()
        cases = evidence["cases"]

        self.assertEqual([case["size"] for case in cases], [16, 32, 64])
        for case in cases:
            with self.subTest(size=case["size"]):
                size = case["size"]
                authority = size * size * 4
                edit_count = size * size
                preview_width = size * 2
                preview_height = size * 2

                self.assertEqual(case["authoritative_storage_payload_bytes"], authority)
                self.assertEqual(case["explicit_owned_snapshot_payload_bytes"], authority)
                self.assertEqual(case["full_batch_edit_count"], edit_count)
                self.assertEqual(case["transaction_staging_payload_bytes"], edit_count * 8)
                self.assertEqual(case["transaction_staging_payload_bytes"], authority * 2)
                self.assertEqual(case["preview_width"], preview_width)
                self.assertEqual(case["preview_height"], preview_height)
                self.assertEqual(
                    case["preview_raster_payload_bytes"],
                    preview_width * preview_height * 4,
                )
                self.assertEqual(
                    case["preview_row_buffer_payload_bytes"],
                    preview_width * 4,
                )
                self.assertLess(
                    case["preview_row_buffer_payload_bytes"],
                    case["preview_raster_payload_bytes"],
                )

    def test_runtime_report_is_environment_labelled_without_performance_thresholds(self) -> None:
        report = build_runtime_report(iterations=1)

        self.assertEqual(report["schema"], REPORT_SCHEMA)
        self.assertEqual(
            report["scope"],
            "engineering-microbenchmark-not-portable-performance-claim",
        )
        environment = report["environment"]
        self.assertTrue(environment["python_implementation"])
        self.assertTrue(environment["python_version"])
        self.assertTrue(environment["platform"])
        self.assertEqual(environment["allocation_probe"], "tracemalloc")
        self.assertEqual(environment["timing_clock"], "perf_counter_ns")

        runtime_cases = report["runtime_cases"]
        self.assertEqual([case["size"] for case in runtime_cases], [16, 32, 64])
        for case in runtime_cases:
            with self.subTest(size=case["size"]):
                size = case["size"]
                allocation = case["allocation"]
                timing = case["timing"]
                self.assertEqual(
                    allocation["set_pixels_full_canvas"]["staging_payload_bytes"],
                    size * size * 8,
                )
                for measurement in allocation.values():
                    self.assertGreaterEqual(measurement["retained_extra_bytes"], 0)
                    self.assertGreaterEqual(measurement["peak_extra_bytes"], 0)
                    self.assertGreaterEqual(
                        measurement["peak_extra_bytes"],
                        measurement["retained_extra_bytes"],
                    )
                for measurement in timing.values():
                    self.assertEqual(measurement["iterations"], 1)
                    self.assertGreaterEqual(measurement["min_ns"], 0)
                    self.assertGreaterEqual(measurement["median_ns"], 0)
                    self.assertGreaterEqual(measurement["max_ns"], 0)


if __name__ == "__main__":
    unittest.main()
