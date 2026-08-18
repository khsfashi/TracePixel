from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from evidence.g8_h4.preview_repair_authoring import (
    REPAIR_PREVIEW_SCALE,
    run_preview_repair_authoring,
)
from tracepixel.agent import AGENT_PROVIDER_PROPOSAL_SCHEMA_V1, AgentProviderUsage
from tracepixel.model import PIXEL_PROGRAM_SCHEMA_V1


def _connected_humanoid_pixels() -> list[list[int]]:
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


class _RepairFixtureProvider:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self._usage: AgentProviderUsage | None = None

    def propose(self, request):
        self.requests.append(request)
        call = len(self.requests)
        self._usage = AgentProviderUsage(input_tokens=1000 + call, output_tokens=300 + call)

        if call == 1:
            pixels = _connected_humanoid_pixels()
            pixels.append([27, 8, 122, 88, 52, 255])
        elif call == 2:
            observation = request["observation"]
            preview = observation["preview"]
            if preview is None:
                raise AssertionError("repair request must carry the current canvas preview")
            if preview["width"] != 32 * REPAIR_PREVIEW_SCALE:
                raise AssertionError("repair preview width mismatch")
            if preview["height"] != 32 * REPAIR_PREVIEW_SCALE:
                raise AssertionError("repair preview height mismatch")
            if "exactly 16 visible RGBA colors" not in request["instruction"]:
                raise AssertionError("repair request lost the frozen palette guidance")
            if "Do not redraw the whole sprite" not in request["instruction"]:
                raise AssertionError("repair request lost local-edit guidance")
            pixels = [[27, 8, 0, 0, 0, 0]]
        else:
            raise AssertionError("fixture should finish after one local repair")

        return {
            "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
            "kind": "pixel_program",
            "payload": {
                "schema": PIXEL_PROGRAM_SCHEMA_V1,
                "canvas": {"width": 32, "height": 32},
                "operations": [{"op": "set_pixels", "pixels": pixels}],
            },
        }

    def last_usage(self, /) -> AgentProviderUsage | None:
        return self._usage


class G8H4PreviewRepairTests(unittest.TestCase):
    def test_remaining_connectivity_finding_gets_current_preview_and_local_repair(self) -> None:
        provider = _RepairFixtureProvider()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "retained"
            summary = run_preview_repair_authoring(
                output,
                lambda: provider,
                source_sha="2" * 40,
            )

            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(len(provider.requests), 2)
            repair_observation = provider.requests[1]["observation"]
            self.assertEqual(repair_observation["current"]["revision"], 1)
            self.assertIsNotNone(repair_observation["preview"])

            qa = json.loads((output / "qa-history.json").read_text(encoding="utf-8"))
            self.assertNotEqual(qa["evaluations"][1]["findings"], [])
            self.assertEqual(qa["final_findings"], [])

            telemetry = json.loads((output / "telemetry.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(telemetry["visual_observation_calls"], 2)

            complexity = json.loads((output / "complexity.json").read_text(encoding="utf-8"))
            self.assertEqual(complexity["provider_calls"], 2)
            self.assertEqual(complexity["repair_vs_regeneration"]["repair_provider_calls"], 1)
            self.assertEqual(complexity["repair_vs_regeneration"]["regeneration_provider_calls"], 0)
            self.assertEqual(complexity["repair_vs_regeneration"]["canvas_restarts"], 0)


if __name__ == "__main__":
    unittest.main()
