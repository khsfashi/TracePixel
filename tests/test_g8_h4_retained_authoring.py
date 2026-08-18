from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from evidence.g8_h4.retained_authoring import P10_C4_BASELINE, run_retained_authoring
from tracepixel.agent import AGENT_PROVIDER_PROPOSAL_SCHEMA_V1, AgentProviderUsage
from tracepixel.model import PIXEL_PROGRAM_SCHEMA_V1


def _humanoid_pixels() -> list[list[int]]:
    pixels: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    skin = (202, 158, 112, 255)
    cloth = (70, 94, 128, 255)
    dark = (34, 39, 48, 255)
    spear = (122, 88, 52, 255)

    def rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int, int]) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                pixels[(x, y)] = color

    rect(15, 5, 19, 9, skin)
    pixels[(20, 8)] = skin
    pixels[(18, 7)] = dark
    rect(14, 10, 19, 18, cloth)
    rect(11, 11, 14, 16, cloth)
    pixels[(11, 17)] = skin
    rect(19, 11, 21, 15, cloth)
    pixels[(21, 16)] = skin
    rect(14, 18, 16, 25, cloth)
    rect(17, 18, 19, 25, cloth)
    rect(13, 25, 16, 26, dark)
    rect(17, 25, 20, 26, dark)
    for y in range(7, 28):
        pixels[(22, y)] = spear
    pixels[(21, 16)] = skin
    pixels[(22, 16)] = spear
    pixels[(22, 7)] = dark
    pixels[(22, 27)] = dark

    return [[x, y, *color] for (x, y), color in sorted(pixels.items(), key=lambda item: (item[0][1], item[0][0]))]


class _FixtureProvider:
    def __init__(self) -> None:
        self.calls = 0
        self._usage: AgentProviderUsage | None = None

    def propose(self, request):
        self.calls += 1
        if self.calls != 1:
            raise AssertionError("fixture should finish after one provider proposal")
        self._usage = AgentProviderUsage(input_tokens=900, output_tokens=300)
        return {
            "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
            "kind": "pixel_program",
            "payload": {
                "schema": PIXEL_PROGRAM_SCHEMA_V1,
                "canvas": {"width": 32, "height": 32},
                "operations": [
                    {
                        "op": "set_pixels",
                        "pixels": _humanoid_pixels(),
                    }
                ],
            },
        }

    def last_usage(self, /) -> AgentProviderUsage | None:
        return self._usage


class G8H4RetainedAuthoringTests(unittest.TestCase):
    def test_provider_free_fixture_reuses_h0_h3_contracts_and_retains_h5_review_evidence(self) -> None:
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
            self.assertEqual(summary["asset_class"], "static-humanoid-character")
            self.assertTrue(summary["profile_reused"])
            self.assertTrue(summary["pose_reused"])
            self.assertFalse(summary["deterministic_qa_is_visual_quality_success"])
            self.assertFalse(summary["new_schema_or_contract_added"])
            self.assertFalse(summary["new_raster_authority_added"])
            self.assertFalse(summary["animation_advanced"])
            self.assertFalse(summary["trace2d_integration_advanced"])

            self.assertTrue((output / "final.png").is_file())
            self.assertTrue((output / "preview-8x.png").is_file())
            self.assertTrue((output / "stage-index.json").is_file())
            self.assertTrue((output / "review-package" / "index.html").is_file())
            self.assertTrue((output / "review-package" / "index.ko.html").is_file())
            self.assertTrue((output / "review-package" / "H5_REVIEW.md").is_file())

            stages = json.loads((output / "stage-index.json").read_text(encoding="utf-8"))["stages"]
            self.assertGreaterEqual(len(stages), 2)
            self.assertFalse(stages[-1]["semantic_stage_claimed"])

            complexity = json.loads((output / "complexity.json").read_text(encoding="utf-8"))
            self.assertEqual(complexity["provider_calls"], 1)
            self.assertEqual(complexity["input_tokens"], 900)
            self.assertEqual(complexity["output_tokens"], 300)
            self.assertEqual(complexity["iterations"], 1)
            self.assertEqual(complexity["revisions"], 1)
            self.assertGreater(complexity["pixel_edits"], 0)
            self.assertGreater(complexity["changed_pixels"], 0)
            self.assertEqual(complexity["deterministic_qa"]["final_findings"], [])
            self.assertEqual(complexity["repair_vs_regeneration"]["regeneration_provider_calls"], 0)
            self.assertTrue(complexity["cache_or_profile_reuse"]["humanoid_profile_reused"])
            self.assertTrue(complexity["cache_or_profile_reuse"]["pose_profile_reused"])
            self.assertEqual(complexity["cache_or_profile_reuse"]["profile_research_provider_calls"], 0)
            self.assertEqual(complexity["hidden_scheduler_provider_calls"], 0)
            self.assertFalse(complexity["second_raster_authority"])
            self.assertFalse(complexity["skeletal_or_ik_authority_added"])
            self.assertFalse(complexity["equipment_specific_raster_authority_added"])
            self.assertEqual(
                complexity["p10_c4_comparison"]["baseline_facts"]["input_tokens"],
                P10_C4_BASELINE["input_tokens"],
            )
            self.assertEqual(provider.calls, 1)


if __name__ == "__main__":
    unittest.main()
