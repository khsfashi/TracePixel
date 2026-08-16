from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Sequence

from tracepixel.agent import (
    AGENT_LOOP_BUDGET_SCHEMA_V1,
    CODEX_CLI_MODEL_V1,
    CODEX_CLI_REASONING_EFFORT_V1,
    CodexCliProvider,
    run_bounded_edit_loop_with_telemetry,
)
from tracepixel.model import ART_INTENT_SCHEMA_V1
from tracepixel.qa import (
    QA_POLICY_SCHEMA_V1,
    analyze_color,
    analyze_connectivity,
    analyze_shape_outline,
    analyze_structural,
    evaluate_qa_policy,
)
from tracepixel.raster import Canvas, export_native_png, export_nearest_preview_png

SUMMARY_SCHEMA_V1 = "tracepixel.p5-a5-codex-smoke.v1"
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("reference-run")

_ART_INTENT = {
    "schema": ART_INTENT_SCHEMA_V1,
    "asset_class": "health-potion-icon",
    "canvas": {"width": 16, "height": 16},
    "composition": {
        "occupied_bounds": {"x": 3, "y": 2, "width": 10, "height": 13},
        "facing": "front",
        "symmetry": {"axis": "vertical", "strength": "required"},
        "light_direction": "top_left",
        "palette_budget": 6,
    },
}

_BUDGET = {
    "schema": AGENT_LOOP_BUDGET_SCHEMA_V1,
    "max_iterations": 4,
    "max_tool_calls": 4,
    "max_operations": 16,
    "max_pixel_edits": 256,
}

_INSTRUCTION = (
    "Create a readable 16x16 red health-potion pixel icon on transparent black. "
    "Keep all visible pixels opaque, keep visible content off the canvas edges, use at most six "
    "visible RGBA colors, keep the visible shape as one 4-connected component with no isolated "
    "pixels, and make the visibility mask vertically symmetric. Use the compact intent and QA "
    "findings to revise only when deterministic QA still reports a failure."
)


class _SmokeQa:
    _policy = {
        "schema": QA_POLICY_SCHEMA_V1,
        "rules": [
            {"rule": "structural.non_empty", "severity": "error"},
            {"rule": "structural.no_translucency", "severity": "error"},
            {"rule": "structural.no_edge_contact", "severity": "error"},
            {"rule": "color.maximum_colors", "severity": "error"},
            {"rule": "color.transparent_rgb_policy", "severity": "error"},
            {"rule": "connectivity.single_component", "severity": "error"},
            {"rule": "connectivity.no_isolated_pixels", "severity": "error"},
            {"rule": "shape.required_symmetry", "severity": "error"},
        ],
    }

    def evaluate(self, canvas: Canvas):
        return evaluate_qa_policy(
            self._policy,
            structural=analyze_structural(canvas),
            color=analyze_color(
                canvas,
                max_colors=6,
                transparent_rgb_policy="require_zero",
            ),
            connectivity=analyze_connectivity(canvas),
            shape_outline=analyze_shape_outline(canvas, required_symmetry="vertical"),
        )


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise SystemExit("P5-A5 reference smoke must run from a Git checkout with a resolvable HEAD")
    return result.stdout.strip()


def run_smoke(output_dir: Path) -> dict[str, object]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty evidence directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = CodexCliProvider()
    environment = provider.environment()
    canvas = Canvas(16, 16)
    result = run_bounded_edit_loop_with_telemetry(
        provider,
        canvas=canvas,
        art_intent=_ART_INTENT,
        instruction=_INSTRUCTION,
        qa_evaluator=_SmokeQa(),
        budget=_BUDGET,
    )
    remaining_findings = result.loop.observation["qa"]["findings"]
    if result.loop.status != "finished" or remaining_findings:
        raise SystemExit(
            "P5-A5 real-provider smoke did not finish cleanly: "
            f"status={result.loop.status!r}, findings={remaining_findings!r}"
        )

    native = export_native_png(canvas)
    preview = export_nearest_preview_png(canvas, scale=8)
    rgba = canvas.rgba_bytes()

    (output_dir / "final.rgba").write_bytes(rgba)
    (output_dir / "final.png").write_bytes(native.png)
    (output_dir / "preview-8x.png").write_bytes(preview.png)
    (output_dir / "telemetry.json").write_text(
        json.dumps(result.telemetry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    calls = [
        {
            "proposal": record.proposal,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
        }
        for record in provider.call_records()
    ]
    (output_dir / "provider-calls.json").write_text(
        json.dumps(calls, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary: dict[str, object] = {
        "schema": SUMMARY_SCHEMA_V1,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": _git_commit(),
        "owner_gate_g3": {
            "provider_surface": "openai-codex-cli",
            "auth_mode": environment.auth_mode,
            "billing_boundary": "existing-chatgpt-codex-plan; api-key billing refused",
            "model": environment.model,
            "reasoning_effort": environment.reasoning_effort,
            "vision_input": False,
            "codex_cli_version": environment.version,
            "sandbox": "read-only",
            "ephemeral": True,
        },
        "budget": _BUDGET,
        "loop_status": result.loop.status,
        "final_revision": result.loop.observation["current"]["revision"],
        "remaining_findings": remaining_findings,
        "authoritative_rgba_sha256": sha256(rgba).hexdigest(),
        "native_png": native.metadata.as_dict(),
        "preview_png": preview.metadata.as_dict(),
        "telemetry_file": "telemetry.json",
        "provider_calls_file": "provider-calls.json",
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the owner-triggered P5-A5 Codex CLI smoke.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Evidence directory; must be absent or empty.",
    )
    args = parser.parse_args(argv)
    summary = run_smoke(args.output_dir)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":
    main()
