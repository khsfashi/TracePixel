from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Sequence

from tracepixel.qa import (
    QA_POLICY_SCHEMA_V1,
    analyze_color,
    analyze_connectivity,
    analyze_shape_outline,
    analyze_structural,
    evaluate_qa_policy,
)
from tracepixel.raster import Canvas, export_native_png, export_nearest_preview_png

SCHEMA = "tracepixel.raw-raster-baseline.v1"
CANVAS_WIDTH = 32
CANVAS_HEIGHT = 32
PREVIEW_SCALE = 8
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "low"
TIMEOUT_SECONDS = 180
MAX_PROVIDER_CALLS = 1
MAX_INPUT_TOKENS = 18_943
MAX_OUTPUT_TOKENS = 3_548
PALETTE_BUDGET = 16
DIRECT_RUN_ID = 32118899233

RAW_TASK = (
    "Create exactly one 32x32 transparent-background pixel-art humanoid adventurer. "
    "The character is in a grounded three-quarter-right guard pose, with both feet grounded and both arms and legs "
    "readable. The right hand visibly holds one short spear in front of the body; the left hand is visibly free. "
    "Use an asymmetric high side-plume as the main identity feature. Read materials as matte teal cloth, warm dark-brown "
    "leather, and cool gray metal for the spearhead, with top-left light. Favor a strong silhouette, believable coarse "
    "anatomy, broad coherent 2-4px clusters, and clear material separation over micro-detail. Keep all visible pixels opaque, "
    "use at most 16 visible colors, keep the visible sprite off the outer canvas edge, and avoid isolated/confetti pixels. "
    "Emit only non-transparent pixels. Return raw raster pixel data only; do not return PixelProgram operations, staged plans, "
    "humanoid profile/pose contracts, repair instructions, or explanations."
)

_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema", "canvas", "pixels"],
    "properties": {
        "schema": {"type": "string", "const": SCHEMA},
        "canvas": {
            "type": "object",
            "additionalProperties": False,
            "required": ["width", "height"],
            "properties": {
                "width": {"type": "integer", "const": CANVAS_WIDTH},
                "height": {"type": "integer", "const": CANVAS_HEIGHT},
            },
        },
        "pixels": {
            "type": "array",
            "maxItems": CANVAS_WIDTH * CANVAS_HEIGHT,
            "items": {
                "type": "array",
                "minItems": 6,
                "maxItems": 6,
                "items": {"type": "integer"},
            },
        },
    },
}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _command(executable: str, arguments: list[str]) -> list[str]:
    if Path(executable).suffix.lower() in (".cmd", ".bat"):
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        command_line = subprocess.list2cmdline([executable, *arguments])
        return [comspec, "/d", "/s", "/c", command_line]
    return [executable, *arguments]


def _metadata(executable: str, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        _command(executable, arguments),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail[-2000:] or f"Codex metadata command exited {result.returncode}")
    return result


def _usage_from_jsonl(stdout: str) -> tuple[int | None, int | None]:
    last: tuple[int | None, int | None] = (None, None)
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if type(event) is not dict or event.get("type") != "turn.completed":
            continue
        usage = event.get("usage")
        if type(usage) is not dict:
            continue
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        last = (
            input_tokens if type(input_tokens) is int and input_tokens >= 0 else None,
            output_tokens if type(output_tokens) is int and output_tokens >= 0 else None,
        )
    return last


def _run_provider(output_root: Path) -> tuple[dict[str, object], dict[str, object]]:
    executable = shutil.which("codex")
    if executable is None:
        raise RuntimeError("cannot find 'codex' on PATH")

    version_result = _metadata(executable, ["--version"])
    version = (version_result.stdout or version_result.stderr).strip()
    auth_result = _metadata(executable, ["login", "status"])
    auth_text = "\n".join(part.strip() for part in (auth_result.stdout, auth_result.stderr) if part.strip())
    if "Logged in using ChatGPT" not in auth_text or "Logged in using an API key" in auth_text:
        raise RuntimeError("matched RAW baseline requires existing ChatGPT Codex login; API-key billing is forbidden")

    prompt = (
        "You are the RAW matched authoring baseline. Do not inspect the filesystem, run shell commands, or explain. "
        "Author the requested sprite directly as sparse raw RGBA8 pixel data. The JSON schema is the only output contract; "
        "there is no TracePixel staged controller, PixelProgram authoring operation, humanoid-specific contract, or repair loop.\n"
        f"TASK={RAW_TASK}"
    )

    with tempfile.TemporaryDirectory(prefix="tracepixel-g8-raw-") as temporary:
        directory = Path(temporary)
        schema_path = directory / "raw.schema.json"
        output_path = directory / "raw.json"
        schema_path.write_text(json.dumps(_OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        command = _command(
            executable,
            [
                "exec",
                "--ephemeral",
                "--json",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--model",
                MODEL,
                "--config",
                f"model_reasoning_effort={REASONING_EFFORT}",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-",
            ],
        )
        started = time.perf_counter_ns()
        result = subprocess.run(
            command,
            input=prompt,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        provider_wall_time_ns = time.perf_counter_ns() - started
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail[-4000:] or f"Codex exited {result.returncode}")
        raw_text = output_path.read_text(encoding="utf-8")
        response = json.loads(raw_text)
        if type(response) is not dict:
            raise RuntimeError("RAW response must be a JSON object")
        input_tokens, output_tokens = _usage_from_jsonl(result.stdout)

    _write_json(output_root / "provider-request.json", {"schema": "tracepixel.raw-baseline-request.v1", "task": RAW_TASK})
    _write_json(output_root / "provider-response.json", response)
    provider = {
        "provider_calls": 1,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "provider_wall_time_ns": provider_wall_time_ns,
        "version": version,
        "auth_mode": "chatgpt",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
    }
    return response, provider


def _canvas_from_response(response: dict[str, object]) -> tuple[Canvas, int]:
    if response.get("schema") != SCHEMA:
        raise RuntimeError("RAW response schema mismatch")
    canvas_decl = response.get("canvas")
    if canvas_decl != {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT}:
        raise RuntimeError("RAW response canvas mismatch")
    raw_pixels = response.get("pixels")
    if type(raw_pixels) is not list or not raw_pixels:
        raise RuntimeError("RAW response must contain visible pixels")

    canvas = Canvas(CANVAS_WIDTH, CANVAS_HEIGHT)
    seen: set[tuple[int, int]] = set()
    edits: list[tuple[int, int, tuple[int, int, int, int]]] = []
    for raw in raw_pixels:
        if type(raw) is not list or len(raw) != 6 or any(type(value) is not int for value in raw):
            raise RuntimeError("RAW pixels must be [x,y,r,g,b,a] integer records")
        x, y, red, green, blue, alpha = raw
        if not (0 <= x < CANVAS_WIDTH and 0 <= y < CANVAS_HEIGHT):
            raise RuntimeError("RAW pixel coordinate out of bounds")
        if not all(0 <= value <= 255 for value in (red, green, blue, alpha)):
            raise RuntimeError("RAW pixel channel out of RGBA8 range")
        if alpha != 255:
            raise RuntimeError("RAW baseline must omit transparent pixels and keep listed pixels opaque")
        key = (x, y)
        if key in seen:
            raise RuntimeError("RAW baseline forbids duplicate pixel coordinates")
        seen.add(key)
        edits.append((x, y, (red, green, blue, alpha)))
    canvas.set_pixels(edits)
    return canvas, len(edits)


def _qa(canvas: Canvas) -> dict[str, object]:
    policy = {
        "schema": QA_POLICY_SCHEMA_V1,
        "rules": [
            {"rule": "structural.non_empty", "severity": "error"},
            {"rule": "structural.no_translucency", "severity": "error"},
            {"rule": "structural.no_edge_contact", "severity": "error"},
            {"rule": "color.maximum_colors", "severity": "error"},
            {"rule": "color.transparent_rgb_policy", "severity": "error"},
            {"rule": "connectivity.single_component", "severity": "error"},
            {"rule": "connectivity.no_isolated_pixels", "severity": "error"},
        ],
    }
    return evaluate_qa_policy(
        policy,
        structural=analyze_structural(canvas),
        color=analyze_color(canvas, max_colors=PALETTE_BUDGET, transparent_rgb_policy="require_zero"),
        connectivity=analyze_connectivity(canvas),
        shape_outline=analyze_shape_outline(canvas),
    )


def run(output_root: Path, *, source_sha: str) -> dict[str, object]:
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty output directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    total_started = time.perf_counter_ns()
    response, provider = _run_provider(output_root)
    canvas, pixel_edits = _canvas_from_response(response)
    findings = _qa(canvas)
    native = export_native_png(canvas)
    preview = export_nearest_preview_png(canvas, scale=PREVIEW_SCALE)
    (output_root / "final.png").write_bytes(native.png)
    (output_root / f"preview-{PREVIEW_SCALE}x.png").write_bytes(preview.png)
    total_wall_time_ns = time.perf_counter_ns() - total_started

    input_tokens = provider["input_tokens"]
    output_tokens = provider["output_tokens"]
    budget_checks = {
        "provider_calls": provider["provider_calls"] <= MAX_PROVIDER_CALLS,
        "input_tokens": type(input_tokens) is int and input_tokens <= MAX_INPUT_TOKENS,
        "output_tokens": type(output_tokens) is int and output_tokens <= MAX_OUTPUT_TOKENS,
    }
    telemetry = {
        **provider,
        "iterations": 1,
        "revisions": 1,
        "pixel_edits": pixel_edits,
        "changed_pixels": pixel_edits,
        "repair_provider_calls": 0,
        "deterministic_qa_evaluations": 1,
        "deterministic_qa_final_findings": findings["findings"],
        "total_wall_time_ns": total_wall_time_ns,
    }
    _write_json(output_root / "telemetry.json", telemetry)
    _write_json(output_root / "qa.json", findings)
    _write_json(
        output_root / "budget-guard.json",
        {
            "matched_against_run_id": DIRECT_RUN_ID,
            "ceilings": {
                "provider_calls": MAX_PROVIDER_CALLS,
                "input_tokens": MAX_INPUT_TOKENS,
                "output_tokens": MAX_OUTPUT_TOKENS,
            },
            "checks": budget_checks,
            "passed": all(budget_checks.values()),
        },
    )
    summary = {
        "schema": "tracepixel.g8-raw-matched-baseline-result.v1",
        "source_sha": source_sha.lower(),
        "baseline_kind": "raw-direct-raster",
        "matched_tracepixel_run_id": DIRECT_RUN_ID,
        "task_fixture": "32x32 fixture adventurer / three-quarter-right guard / right-hand short spear / left hand clear",
        "provider": {key: provider[key] for key in ("version", "auth_mode", "model", "reasoning_effort")},
        "provider_calls": 1,
        "iterations": 1,
        "repair_provider_calls": 0,
        "pixel_edits": pixel_edits,
        "deterministic_qa_passed": not findings["findings"],
        "owner_quality_status": "pending-review",
        "no_tracepixel_staged_controller": True,
        "no_humanoid_specific_contract": True,
        "no_pixelprogram_authoring": True,
        "no_repair_loop": True,
        "g9_animation_advanced": False,
        "trace2d_integration_advanced": False,
    }
    _write_json(output_root / "summary.json", summary)
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args(argv)
    try:
        summary = run(args.output, source_sha=args.source_sha)
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        _write_json(
            args.output / "failure.json",
            {
                "schema": "tracepixel.g8-raw-matched-baseline-failure.v1",
                "source_sha": args.source_sha.lower(),
                "failure_type": type(exc).__name__,
                "message": str(exc),
                "provider_retry_permitted": False,
                "g9_animation_advanced": False,
                "trace2d_integration_advanced": False,
            },
        )
        return 1
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
