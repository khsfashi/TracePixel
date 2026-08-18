from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from evidence.g8_h4.reconcile_success_candidate import (
    CANDIDATE_RUN_ID,
    EXPECTED_CUMULATIVE,
    FAILED_RUN_ID,
    reconcile_downloaded_directories,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _attempt(
    *,
    provider_calls: int,
    input_tokens: int,
    output_tokens: int,
    iterations: int,
    operation_calls: int,
    pixel_edits: int,
    repair_calls: int,
    wall_time_ns: int,
) -> dict[str, object]:
    return {
        "provider_calls": provider_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "iterations": iterations,
        "revisions": iterations,
        "operation_calls": operation_calls,
        "pixel_edits": pixel_edits,
        "changed_pixels": pixel_edits,
        "repair_vs_regeneration": {
            "repair_provider_calls": repair_calls,
            "regeneration_provider_calls": 0,
            "canvas_restarts": 0,
        },
        "cache_or_profile_reuse": {
            "humanoid_profile_reused": True,
            "pose_profile_reused": True,
            "profile_research_provider_calls": 0,
        },
        "wall_time_ns": wall_time_ns,
    }


class G8H4CandidateReconciliationTests(unittest.TestCase):
    def test_failed_attempt_and_success_candidate_are_cumulative_without_provider_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            failed = root / "failed"
            candidate = root / "candidate"
            output = root / "output"

            _write_json(
                failed / "attempt-complexity.json",
                _attempt(
                    provider_calls=4,
                    input_tokens=72974,
                    output_tokens=15512,
                    iterations=4,
                    operation_calls=4,
                    pixel_edits=1182,
                    repair_calls=3,
                    wall_time_ns=420035405800,
                ),
            )
            _write_json(
                failed / "summary.json",
                {
                    "source_sha": "accb144a52b5acafcf2fbe6be3d2c3acfdeda095",
                    "status": "failed",
                    "owner_verdict": "pending",
                },
            )

            _write_json(
                candidate / "attempt-complexity.json",
                _attempt(
                    provider_calls=1,
                    input_tokens=18943,
                    output_tokens=3548,
                    iterations=1,
                    operation_calls=1,
                    pixel_edits=268,
                    repair_calls=0,
                    wall_time_ns=97756393400,
                ),
            )
            _write_json(candidate / "complexity.json", {"stale_single_attempt": True})
            _write_json(
                candidate / "summary.json",
                {
                    "source_sha": "accb144a52b5acafcf2fbe6be3d2c3acfdeda095",
                    "status": "succeeded",
                    "owner_verdict": "pending",
                    "new_schema_or_contract_added": False,
                    "new_raster_authority_added": False,
                    "animation_advanced": False,
                    "trace2d_integration_advanced": False,
                },
            )
            for relative in (
                "final.png",
                "preview-8x.png",
                "stage-index.json",
                "review-package/index.html",
                "review-package/index.ko.html",
                "review-package/H5_REVIEW.md",
            ):
                path = candidate / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")

            result = reconcile_downloaded_directories(candidate, failed, output)
            complexity = result["complexity"]
            self.assertEqual(complexity["candidate_run_id"], CANDIDATE_RUN_ID)
            self.assertEqual(
                [item["run_id"] for item in complexity["included_attempts"]],
                [FAILED_RUN_ID, CANDIDATE_RUN_ID],
            )
            for field in (
                "attempt_count",
                "provider_calls",
                "input_tokens",
                "output_tokens",
                "iterations",
                "revisions",
                "operation_calls",
                "pixel_edits",
                "changed_pixels",
                "wall_time_ns",
            ):
                self.assertEqual(complexity[field], EXPECTED_CUMULATIVE[field])
            self.assertEqual(
                complexity["repair_vs_regeneration"]["repair_provider_calls"],
                EXPECTED_CUMULATIVE["repair_provider_calls"],
            )
            self.assertEqual(
                complexity["repair_vs_regeneration"]["regeneration_provider_calls"],
                0,
            )
            self.assertEqual(result["reconciliation"]["provider_calls_added_by_reconciliation"], 0)
            self.assertEqual(result["reconciliation"]["h5_owner_acceptance_state"], "pending")


if __name__ == "__main__":
    unittest.main()
