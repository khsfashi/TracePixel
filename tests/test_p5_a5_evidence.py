from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from tracepixel.agent import (
    validate_agent_complexity_telemetry,
    validate_agent_provider_proposal,
)
from tracepixel.model import execute_pixel_program
from tracepixel.raster import export_native_png, export_nearest_preview_png


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "p5_a5" / "reference-run"


class P5A5EvidenceTests(unittest.TestCase):
    def test_reference_manifest_and_complexity_are_bounded(self) -> None:
        manifest = json.loads((EVIDENCE / "manifest.json").read_text(encoding="utf-8"))
        telemetry = json.loads((EVIDENCE / "telemetry.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["schema"], "tracepixel.p5-a5-codex-smoke.v1")
        self.assertEqual(manifest["source_commit"], "c53d934cb6296c27e29455734c747363d9c8254b")
        self.assertEqual(manifest["loop_status"], "finished")
        self.assertEqual(manifest["remaining_findings"], [])
        self.assertEqual(
            manifest["budget"],
            {
                "schema": "tracepixel.agent-loop-budget.v1",
                "max_iterations": 4,
                "max_tool_calls": 4,
                "max_operations": 16,
                "max_pixel_edits": 256,
            },
        )
        self.assertEqual(
            manifest["owner_gate_g3"],
            {
                "provider_surface": "openai-codex-cli",
                "auth_mode": "chatgpt",
                "billing_boundary": "existing-chatgpt-codex-plan; api-key billing refused",
                "model": "gpt-5.6-sol",
                "reasoning_effort": "low",
                "vision_input": False,
                "codex_cli_version": "codex-cli 0.147.0",
                "sandbox": "read-only",
                "ephemeral": True,
            },
        )

        validated = validate_agent_complexity_telemetry(telemetry)
        self.assertEqual(validated["input_tokens"], 16000)
        self.assertEqual(validated["output_tokens"], 1417)
        self.assertEqual(validated["tool_calls"], 1)
        self.assertEqual(validated["iterations"], 1)
        self.assertEqual(validated["operation_calls"], 1)
        self.assertEqual(validated["revisions"], 1)
        self.assertEqual(validated["changed_pixels"], 96)
        self.assertEqual(validated["visual_observation_calls"], 0)
        self.assertEqual(validated["human_interventions"], 0)
        self.assertIsNone(validated["api_cost_usd_micros"])
        self.assertIsNone(validated["failure_category"])

    def test_provider_program_replays_to_exact_committed_raster_and_pngs(self) -> None:
        manifest = json.loads((EVIDENCE / "manifest.json").read_text(encoding="utf-8"))
        calls = json.loads((EVIDENCE / "provider-calls.json").read_text(encoding="utf-8"))

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["input_tokens"], 16000)
        self.assertEqual(calls[0]["output_tokens"], 1417)
        proposal = validate_agent_provider_proposal(calls[0]["proposal"])
        self.assertEqual(proposal["kind"], "pixel_program")

        canvas = execute_pixel_program(proposal["payload"])
        rgba = canvas.rgba_bytes()
        committed_rgba = (EVIDENCE / "final.rgba").read_bytes()
        self.assertEqual(len(committed_rgba), 16 * 16 * 4)
        self.assertEqual(rgba, committed_rgba)
        self.assertEqual(
            hashlib.sha256(rgba).hexdigest(),
            manifest["authoritative_rgba_sha256"],
        )

        native = export_native_png(canvas)
        preview = export_nearest_preview_png(canvas, scale=8)
        self.assertEqual(native.png, (EVIDENCE / "final.png").read_bytes())
        self.assertEqual(preview.png, (EVIDENCE / "preview-8x.png").read_bytes())
        self.assertEqual(native.metadata.png_sha256, manifest["native_png"]["png_sha256"])
        self.assertEqual(preview.metadata.png_sha256, manifest["preview_png"]["png_sha256"])


if __name__ == "__main__":
    unittest.main()
