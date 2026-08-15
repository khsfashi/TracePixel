from __future__ import annotations

import json
import unittest
from pathlib import Path

from evidence.p2_ir4.benchmark import (
    EVIDENCE_SCHEMA,
    PUBLIC_OPERATION_VOCABULARY,
    TOKEN_PROXY,
    build_evidence,
)

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "evidence" / "p2_ir4"


class P2IR4EvidenceTests(unittest.TestCase):
    def test_evidence_matches_committed_golden(self) -> None:
        committed = json.loads(
            (EVIDENCE_DIR / "structural.json").read_text(encoding="utf-8")
        )
        generated = build_evidence()

        self.assertEqual(generated["schema"], EVIDENCE_SCHEMA)
        self.assertEqual(generated, committed)

    def test_fixed_fixture_set_proves_compact_exact_batched_replay(self) -> None:
        evidence = build_evidence()

        self.assertEqual(evidence["public_operation_vocabulary"], ["set_pixels"])
        self.assertEqual(PUBLIC_OPERATION_VOCABULARY, ("set_pixels",))
        self.assertEqual(
            evidence["token_proxy"]["definition"],
            TOKEN_PROXY,
        )
        self.assertFalse(evidence["token_proxy"]["actual_model_tokens"])
        self.assertTrue(evidence["all_fixture_replays_equal"])

        fixtures = evidence["fixtures"]
        self.assertEqual(
            [case["fixture"] for case in fixtures],
            ["potion-16", "gem-16", "key-16"],
        )
        for case in fixtures:
            with self.subTest(fixture=case["fixture"]):
                self.assertEqual(case["width"], 16)
                self.assertEqual(case["height"], 16)
                self.assertEqual(case["public_operation_count"], 1)
                self.assertEqual(
                    case["raw_primitive_call_count"],
                    case["edit_count"],
                )
                self.assertTrue(case["exact_replay_equal"])
                self.assertLess(
                    case["canonical_pixel_program_bytes"],
                    case["raw_primitive_call_stream_bytes"],
                )
                self.assertGreater(
                    case["canonical_pixel_program_bytes"],
                    case["bare_edit_array_bytes"],
                )
                self.assertEqual(
                    case["canonical_envelope_over_bare_edits_bytes"],
                    119,
                )

        totals = evidence["totals"]
        self.assertEqual(totals["fixture_count"], 3)
        self.assertEqual(totals["edit_count"], 250)
        self.assertEqual(totals["public_operation_count"], 3)
        self.assertEqual(totals["raw_primitive_call_count"], 250)
        self.assertEqual(totals["canonical_pixel_program_bytes"], 5545)
        self.assertEqual(totals["raw_primitive_call_stream_bytes"], 8269)
        self.assertEqual(totals["bare_edit_array_bytes"], 5188)
        self.assertEqual(totals["canonical_token_proxy"], 1388)
        self.assertEqual(totals["raw_primitive_token_proxy"], 2069)
        self.assertEqual(totals["bare_edit_array_token_proxy"], 1298)
        self.assertEqual(totals["canonical_vs_raw_primitive_saved_bytes"], 2724)
        self.assertEqual(totals["canonical_envelope_over_bare_edits_bytes"], 357)

    def test_invalidity_corpus_covers_all_current_semantic_codes_and_wire_errors(self) -> None:
        invalidity = build_evidence()["invalidity"]
        self.assertTrue(invalidity["all_expected_failures_observed"])

        validation_cases = invalidity["validation_cases"]
        self.assertEqual(
            {case["observed_code"] for case in validation_cases},
            {
                "invalid_type",
                "invalid_fields",
                "unsupported_schema",
                "invalid_canvas",
                "unsupported_operation",
                "invalid_edit",
                "invalid_coordinate",
                "invalid_color",
            },
        )
        self.assertTrue(all(case["rejected"] for case in validation_cases))
        self.assertTrue(all(case["expected_match"] for case in validation_cases))

        wire_cases = invalidity["wire_cases"]
        self.assertEqual(
            [case["observed_code"] for case in wire_cases],
            ["invalid_type", "invalid_json"],
        )
        self.assertTrue(all(case["rejected"] for case in wire_cases))
        self.assertTrue(all(case["expected_match"] for case in wire_cases))

    def test_ir4_keeps_v1_operation_budget_at_one(self) -> None:
        decision = build_evidence()["vocabulary_decision"]
        self.assertEqual(
            decision["decision"],
            "retain-single-set_pixels-operation-for-pixel-program-v1",
        )


if __name__ == "__main__":
    unittest.main()
