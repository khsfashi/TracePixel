from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from evidence.p10_c3.forward_checkpoint import main as c3_forward_main

ROOT = Path(__file__).resolve().parents[2]
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"
WORKFLOW = ROOT / ".github" / "workflows" / "owner-p10-c4-retained-authoring.yml"
AUTHORING = ROOT / "evidence" / "p10_c4" / "retained_authoring.py"


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"P10-C4 checkpoint failed: {message}")


def main() -> int:
    _expect(c3_forward_main() == 0, "P10-C3 historical checkpoint failed")

    lane = json.loads(CORE_LANE.read_text(encoding="utf-8"))
    _expect(type(lane) is dict, "core lane must be a JSON object")
    typed = cast(dict[str, object], lane)
    _expect(typed.get("current") == "P10", "core lane is not P10")
    _expect(typed.get("current_child") == "P10-C4", "core lane is not P10-C4")
    _expect(typed.get("active_issue") == 109, "P10-C4 is not bound to issue #109")

    _expect(AUTHORING.is_file(), "retained authoring entry point is missing")
    _expect(WORKFLOW.is_file(), "trusted owner-run workflow is missing")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    _expect("runs-on: [self-hosted, Windows, X64]" in workflow, "C4 real authoring must stay on trusted self-hosted Windows")
    _expect("github.actor == github.repository_owner" in workflow, "C4 owner gate is missing")
    _expect("Logged in using ChatGPT" in workflow, "C4 ChatGPT Codex auth boundary is missing")
    _expect("Logged in using an API key" in workflow, "C4 API-key rejection boundary is missing")
    _expect("actions/upload-artifact@v4" in workflow, "C4 retained artifact upload is missing")
    _expect("actions/checkout@" not in workflow, "C4 must keep hardened manual checkout")
    _expect("actions/setup-python@" not in workflow, "C4 must keep hardened local Python resolution")

    print(json.dumps({
        "schema": "tracepixel.p10-c4-checkpoint.v1",
        "status": "pass",
        "source_issue": 109,
        "current_child": "P10-C4",
        "next_child": "P10-C5",
        "portable_provider_calls": 0,
        "real_provider_execution": "owner-triggered-only",
        "single_asset_authority_reused": True,
        "new_raster_authority": False,
        "humanoid": False,
        "animation": False,
        "trace2d": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
