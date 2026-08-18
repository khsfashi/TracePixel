from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from evidence.g8_h4.cumulative_complexity import (
    P10_C4_BASELINE,
    aggregate_directories,
    build_cumulative_complexity,
)


def _attempt(
    *,
    run_id: int,
    provider_calls: int,
    input_tokens: int,
    output_tokens: int,
    iterations: int,
    revisions: int,
    operation_calls: int,
    pixel_edits: int,
    changed_pixels: int,
    repair_calls: int,
    regeneration_calls: int,
    wall_time_ns: int,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "source_sha": f"{run_id:040x}"[-40:],
        "status": "succeeded",
        "owner_verdict": "pending",
        "complexity": {
            "provider_calls": provider_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "iterations": iterations,
            "revisions": revisions,
            "operation_calls": operation_calls,
            "pixel_edits": pixel_edits,
            "changed_pixels": changed_pixels,
            "repair_vs_regeneration": {
                "repair_provider_calls": repair_calls,
                "regeneration_provider_calls": regeneration_calls,
                "canvas_restarts": 0,
            },
            "wall_time_ns": wall_time_ns,
            "cache_or_profile_reuse": {
                "humanoid_profile_reused": True,
                "pose_profile_reused": True,
                "profile_research_provider_calls": 0,
            },
        },
    }


class G8H4CumulativeComplexityTests(unittest.TestCase):
    def test_owner_candidate_totals_include_every_retained_attempt_and_compare_raw_usage(self) -> None:
        attempts = [
            _attempt(
                run_id=10,
                provider_calls=1,
                input_tokens=1000,
                output_tokens=200,
                iterations=1,
                revisions=1,
                operation_calls=1,
                pixel_edits=100,
                changed_pixels=90,
                repair_calls=0,
                regeneration_calls=0,
                wall_time_ns=10_000,
            ),
            _attempt(
                run_id=11,
                provider_calls=2,
                input_tokens=2000,
                output_tokens=400,
                iterations=2,
                revisions=2,
                operation_calls=2,
                pixel_edits=200,
                changed_pixels=150,
                repair_calls=1,
                regeneration_calls=0,
                wall_time_ns=20_000,
            ),
        ]
        cumulative = build_cumulative_complexity(attempts, candidate_run_id=11)

        self.assertEqual(cumulative["owner_acceptance_state"], "pending")
        self.assertEqual(cumulative["attempt_count"], 2)
        self.assertEqual(cumulative["provider_calls"], 3)
        self.assertEqual(cumulative["input_tokens"], 3000)
        self.assertEqual(cumulative["output_tokens"], 600)
        self.assertEqual(cumulative["iterations"], 3)
        self.assertEqual(cumulative["revisions"], 3)
        self.assertEqual(cumulative["operation_calls"], 3)
        self.assertEqual(cumulative["pixel_edits"], 300)
        self.assertEqual(cumulative["changed_pixels"], 240)
        self.assertEqual(cumulative["repair_vs_regeneration"]["repair_provider_calls"], 1)
        self.assertEqual(cumulative["repair_vs_regeneration"]["regeneration_provider_calls"], 0)
        self.assertEqual(cumulative["wall_time_ns"], 30_000)
        self.assertTrue(cumulative["cache_or_profile_reuse"]["humanoid_profile_reused_for_all_provider_attempts"])
        self.assertTrue(cumulative["cache_or_profile_reuse"]["pose_profile_reused_for_all_provider_attempts"])
        self.assertEqual(cumulative["authority"]["authoritative_evidence"], "raw-usage-metrics")
        self.assertFalse(cumulative["authority"]["price_fields_used_for_comparison"])

        provider_comparison = cumulative["p10_c4_comparison"]["metrics"]["provider_calls"]
        self.assertEqual(provider_comparison["p10_c4"], 1)
        self.assertEqual(provider_comparison["g8_h4_cumulative"], 3)
        self.assertEqual(provider_comparison["percent_change"], 200.0)
        repair_comparison = cumulative["p10_c4_comparison"]["metrics"]["repair_provider_calls"]
        self.assertIsNone(repair_comparison["percent_change"])
        self.assertEqual(repair_comparison["rate_status"], "undefined-zero-baseline")

    def test_p10_c4_baseline_carries_full_retained_raw_metrics(self) -> None:
        self.assertEqual(P10_C4_BASELINE["iterations"], 1)
        self.assertEqual(P10_C4_BASELINE["revisions"], 1)
        self.assertEqual(P10_C4_BASELINE["wall_time_ns"], 107656174400)
        self.assertTrue(P10_C4_BASELINE["profile_reused"])
        self.assertTrue(P10_C4_BASELINE["pose_reused"])

    def test_directory_aggregation_prefers_per_attempt_evidence_over_prior_cumulative_file(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior = root / "prior" / "100"
            current = root / "current"
            prior.mkdir(parents=True)
            current.mkdir()

            prior_attempt = _attempt(
                run_id=100,
                provider_calls=1,
                input_tokens=10,
                output_tokens=5,
                iterations=1,
                revisions=1,
                operation_calls=1,
                pixel_edits=4,
                changed_pixels=4,
                repair_calls=0,
                regeneration_calls=0,
                wall_time_ns=100,
            )["complexity"]
            current_attempt = _attempt(
                run_id=101,
                provider_calls=1,
                input_tokens=20,
                output_tokens=6,
                iterations=1,
                revisions=1,
                operation_calls=1,
                pixel_edits=5,
                changed_pixels=5,
                repair_calls=0,
                regeneration_calls=0,
                wall_time_ns=200,
            )["complexity"]
            (prior / "attempt-complexity.json").write_text(json.dumps(prior_attempt), encoding="utf-8")
            (prior / "complexity.json").write_text(json.dumps({"provider_calls": 999}), encoding="utf-8")
            (current / "attempt-complexity.json").write_text(json.dumps(current_attempt), encoding="utf-8")

            cumulative = aggregate_directories(current, root / "prior", current_run_id=101)
            self.assertEqual(cumulative["provider_calls"], 2)
            self.assertEqual(cumulative["input_tokens"], 30)
            self.assertEqual(cumulative["wall_time_ns"], 300)


if __name__ == "__main__":
    unittest.main()
