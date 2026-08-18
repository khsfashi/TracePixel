from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from evidence.p10_c4.retained_authoring import run_retained_authoring
from tracepixel.agent import AGENT_PROVIDER_PROPOSAL_SCHEMA_V1, AgentProviderUsage
from tracepixel.model import PIXEL_PROGRAM_SCHEMA_V1


def _creature_pixels() -> list[list[int]]:
    pixels: list[list[int]] = []
    body = (92, 118, 72, 255)
    dark = (28, 35, 24, 255)

    def rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int, int]) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                pixels.append([x, y, *color])

    rect(7, 11, 20, 19, body)
    rect(19, 9, 25, 15, body)
    for x0 in (9, 13, 17, 20):
        rect(x0, 19, x0 + 1, 25, body)
    pixels.append([23, 11, *dark])
    return pixels


class _FixtureProvider:
    def __init__(self) -> None:
        self.calls = 0
        self._usage: AgentProviderUsage | None = None

    def propose(self, request):
        self.calls += 1
        if self.calls != 1:
            raise AssertionError("fixture should finish after one provider proposal")
        self._usage = AgentProviderUsage(input_tokens=640, output_tokens=220)
        return {
            "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
            "kind": "pixel_program",
            "payload": {
                "schema": PIXEL_PROGRAM_SCHEMA_V1,
                "canvas": {"width": 32, "height": 32},
                "operations": [
                    {
                        "op": "set_pixels",
                        "pixels": _creature_pixels(),
                    }
                ],
            },
        }

    def last_usage(self, /) -> AgentProviderUsage | None:
        return self._usage


class P10C4RetainedAuthoringTests(unittest.TestCase):
    def test_provider_free_fixture_exercises_real_single_asset_authority_and_complexity_evidence(self) -> None:
        provider = _FixtureProvider()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "retained"
            summary = run_retained_authoring(
                output,
                lambda: provider,
                source_sha="1" * 40,
            )

            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(summary["owner_verdict"], "pending")
            self.assertEqual(summary["review_scope"], "retained-output")
            self.assertFalse(summary["new_raster_authority_added"])
            self.assertTrue((output / "final.png").is_file())
            self.assertTrue((output / "preview-8x.png").is_file())
            self.assertTrue((output / "review-package" / "index.html").is_file())
            self.assertTrue((output / "review-package" / "index.ko.html").is_file())

            complexity = json.loads((output / "complexity.json").read_text(encoding="utf-8"))
            self.assertEqual(complexity["provider_calls"], 1)
            self.assertEqual(complexity["input_tokens"], 640)
            self.assertEqual(complexity["output_tokens"], 220)
            self.assertEqual(complexity["iterations"], 1)
            self.assertEqual(complexity["revisions"], 1)
            self.assertGreater(complexity["pixel_edits"], 0)
            self.assertGreater(complexity["changed_pixels"], 0)
            self.assertEqual(complexity["deterministic_qa"]["final_findings"], [])
            self.assertEqual(complexity["repair_vs_regeneration"]["repair_provider_calls"], 0)
            self.assertEqual(complexity["repair_vs_regeneration"]["regeneration_provider_calls"], 0)
            self.assertTrue(complexity["cache_or_profile_reuse"]["morphology_profile_reused"])
            self.assertEqual(complexity["cache_or_profile_reuse"]["profile_research_provider_calls"], 0)
            self.assertIsNone(complexity["failure_category"])
            self.assertEqual(complexity["hidden_scheduler_provider_calls"], 0)
            self.assertFalse(complexity["second_raster_authority"])
            self.assertEqual(provider.calls, 1)


if __name__ == "__main__":
    unittest.main()
