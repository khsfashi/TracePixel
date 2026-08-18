from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from evidence.g8_h3.forward_checkpoint import main as g8_h3_forward_main
from evidence.g8_h4.cumulative_complexity import P10_C4_BASELINE

ROOT = Path(__file__).resolve().parents[2]
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"
H0_CONTRACT = ROOT / "evidence" / "g8_h0" / "promotion-contract.v1.json"
AUTHORING = ROOT / "evidence" / "g8_h4" / "retained_authoring.py"
CUMULATIVE_COMPLEXITY = ROOT / "evidence" / "g8_h4" / "cumulative_complexity.py"
OWNER_WORKFLOW = ROOT / ".github" / "workflows" / "owner-g8-h4-retained-authoring.yml"
STATUS_WORKFLOW = ROOT / ".github" / "workflows" / "g8-h4-owner-authoring-status.yml"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"G8-H4 checkpoint failed: {message}")


def main() -> int:
    _expect(g8_h3_forward_main() == 0, "G8-H3 historical checkpoint failed")
    lane = _json(CORE_LANE)
    contract = _json(H0_CONTRACT)

    _expect(lane.get("current") == "G8", "core lane is not G8")
    _expect(lane.get("current_child") == "G8-H4", "core lane is not G8-H4")
    _expect(lane.get("active_issue") == 119, "G8-H4 is not bound to issue #119")

    contract_lane = cast(dict[str, object], contract.get("lane"))
    _expect(
        contract_lane.get("humanoid_provider_or_raster_earliest_child") == "G8-H4",
        "frozen H0 contract does not authorize H4 as the earliest real authoring child",
    )
    authority = cast(dict[str, object], contract.get("authority"))
    _expect(authority.get("single_asset_pixelprogram_canvas_reused") is True, "single-asset authority reuse drifted")
    _expect(authority.get("second_humanoid_drawing_engine_allowed") is False, "second humanoid drawing engine became allowed")
    _expect(authority.get("skeletal_or_physics_authority_allowed") is False, "skeletal/physics authority became allowed")
    _expect(authority.get("hidden_humanoid_scheduler_provider_work_allowed") is False, "hidden provider scheduling became allowed")

    sequencing = cast(dict[str, object], contract.get("sequencing"))
    _expect(
        sequencing.get("g9_animation") == "blocked-until-g8-static-humanoid-evidence-frozen",
        "G9 animation gate drifted",
    )
    _expect(
        sequencing.get("p9_trace2d") == "requires-explicit-g10-owner-approval",
        "Trace2D gate drifted",
    )

    _expect(AUTHORING.is_file(), "retained authoring entry point is missing")
    _expect(CUMULATIVE_COMPLEXITY.is_file(), "cumulative owner-acceptance complexity entry point is missing")
    _expect(OWNER_WORKFLOW.is_file(), "trusted owner H4 workflow is missing")
    _expect(STATUS_WORKFLOW.is_file(), "H4 status callback workflow is missing")
    for field in (
        "provider_calls",
        "input_tokens",
        "output_tokens",
        "iterations",
        "revisions",
        "operation_calls",
        "pixel_edits",
        "changed_pixels",
        "repair_provider_calls",
        "regeneration_provider_calls",
        "profile_research_provider_calls",
        "wall_time_ns",
    ):
        _expect(field in P10_C4_BASELINE, f"P10-C4 raw comparison baseline is missing {field}")

    print(json.dumps({
        "status": "pass",
        "source_issue": 119,
        "current_child": "G8-H4",
        "next_child": "G8-H5",
        "portable_provider_calls": 0,
        "portable_humanoid_raster_generation": 0,
        "new_contract_or_schema_required": False,
        "single_asset_pixelprogram_canvas_reused": True,
        "complexity_scope": "cumulative-through-owner-acceptable-retained-output",
        "complexity_authority": "raw-usage-metrics",
        "price_conversion_authoritative": False,
        "g9_animation_advanced": False,
        "trace2d_integration_advanced": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
