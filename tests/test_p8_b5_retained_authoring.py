from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evidence.p8_b5.retained_authoring import run_retained_authoring
from tracepixel.agent import (
    AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
    AgentProviderUsage,
)


class _RecordedProvider:
    def __init__(self) -> None:
        self._usage = AgentProviderUsage(input_tokens=5, output_tokens=3)

    def propose(self, request, /):
        intent = request["observation"]["intent"]
        canvas = intent["canvas"]
        width = canvas["width"]
        height = canvas["height"]
        asset_class = intent["asset_class"]
        if asset_class == "terrain-tile":
            coords = [
                [x, y, 90, 130, 70, 255]
                for y in range(height)
                for x in range(width)
            ]
        else:
            x0 = width // 2 - 2
            y0 = height // 2 - 2
            coords = [
                [x, y, 200, 70, 80, 255]
                for y in range(y0, y0 + 4)
                for x in range(x0, x0 + 4)
            ]
        return {
            "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
            "kind": "pixel_program",
            "payload": {
                "schema": "tracepixel.pixel-program.v1",
                "canvas": {"width": width, "height": height},
                "operations": [{"op": "set_pixels", "pixels": coords}],
            },
        }

    def last_usage(self, /) -> AgentProviderUsage:
        return self._usage


class P8B5RetainedAuthoringTests(unittest.TestCase):
    def test_recorded_provider_builds_retained_mobile_review(self) -> None:
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "retained"
            summary = run_retained_authoring(output, _RecordedProvider)

            self.assertEqual(summary["review_scope"], "retained-output")
            self.assertEqual(summary["member_count"], 8)
            self.assertEqual(summary["declared_max_concurrency"], 2)
            self.assertEqual(summary["owner_verdict"], "pending")
            self.assertTrue(summary["owner_review_required_before_p8_b6"])
            self.assertEqual(summary["aggregate_provider_calls"], 8)

            review_manifest = json.loads(
                (output / "review-package" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(review_manifest["review_scope"], "retained-output")
            self.assertEqual(len(review_manifest["members"]), 8)
            self.assertTrue(all(member["source_kind"] == "retained-output" for member in review_manifest["members"]))
            self.assertTrue((output / "review-package" / "index.html").is_file())
            self.assertTrue((output / "review-package" / "index.ko.html").is_file())

            for name in ("p8-b3-report.json", "p8-b4-report.json"):
                report = json.loads((output / "execution" / name).read_text(encoding="utf-8"))
                self.assertEqual(report["declared_max_concurrency"], 2)
                self.assertLessEqual(report["observed_peak_live_members"], 2)
                self.assertEqual(report["scheduler_provider_calls"], 0)
                self.assertEqual(report["failed_member_ids"], [])

    def test_refuses_non_empty_output(self) -> None:
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "retained"
            output.mkdir()
            (output / "keep.txt").write_text("do not overwrite", encoding="utf-8")
            with self.assertRaises(SystemExit):
                run_retained_authoring(output, _RecordedProvider)


if __name__ == "__main__":
    unittest.main()
