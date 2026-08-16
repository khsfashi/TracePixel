from __future__ import annotations

import json
from pathlib import Path

from tracepixel.benchmark import (
    B0_RAW_METHOD_ID,
    B0_TRACEPIXEL_METHOD_ID,
    build_b0_codex_exec_plan,
    build_b0_provider_request,
    build_b0_schedule,
    load_b0_preregistration,
    validate_b0_scored_methods,
)

ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "evidence" / "b0" / "preregistration.v1.json"


def main() -> int:
    preregistration, digest = load_b0_preregistration(FREEZE)
    validate_b0_scored_methods(preregistration)
    schedule = build_b0_schedule(preregistration, preregistration_sha256=digest)

    requests = [
        build_b0_provider_request(preregistration, identity=identity)
        for identity in schedule["attempts"]
    ]
    if len(requests) != 28:
        raise RuntimeError("B0-B0 must materialize all 28 frozen primary adapter requests")

    staged = [request for request in requests if request["attempt"]["method_id"] == B0_TRACEPIXEL_METHOD_ID]
    raw = [request for request in requests if request["attempt"]["method_id"] == B0_RAW_METHOD_ID]
    if len(staged) != 14 or len(raw) != 14:
        raise RuntimeError("B0-B0 must keep the frozen 14/14 method split")
    if any("current_stage" not in request or "method_context" not in request for request in staged):
        raise RuntimeError("TracePixel staged requests must carry stage and visible-derived ArtIntent context")
    if any("current_stage" in request or "method_context" in request for request in raw):
        raise RuntimeError("raw PixelProgram baseline must not receive TracePixel staged context")

    for request in requests:
        encoded = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if "hidden_structural_constraints" in encoded:
            raise RuntimeError("B0-B0 provider request leaked hidden structural constraints")
        plan = build_b0_codex_exec_plan(request)
        if plan["timeout_seconds"] != 180:
            raise RuntimeError("frozen provider timeout drifted")
        if plan["expected_version"] != "codex-cli 0.147.0":
            raise RuntimeError("frozen Codex CLI version drifted")
        if plan["required_auth_marker"] != "Logged in using ChatGPT" or not plan["forbid_api_key_auth"]:
            raise RuntimeError("frozen ChatGPT-auth boundary drifted")
        if "--sandbox" not in plan["command"] or "read-only" not in plan["command"]:
            raise RuntimeError("Codex execution plan must remain read-only")

    summary = {
        "schema": "tracepixel.b0-b0-checkpoint.v1",
        "preregistration_sha256": digest,
        "scheduled_attempts": len(requests),
        "staged_requests": len(staged),
        "raw_requests": len(raw),
        "provider": {
            "surface": "openai-codex-cli",
            "auth_mode": "chatgpt",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "low",
            "codex_cli_version": "codex-cli 0.147.0",
            "vision_input": False,
        },
        "provider_invocations": 0,
        "scored_attempts_started": 0,
        "g4_vlm_crossed": False,
        "g5_aseprite_mcp_crossed": False,
        "g6_self_hosted_runner_crossed": False,
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
