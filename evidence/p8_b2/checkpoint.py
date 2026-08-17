from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import cast

from tracepixel.model.asset_set_consistency_validation import (
    AssetSetConsistencyValidationError,
    build_asset_set_consistency,
    validate_asset_set_consistency,
)

ROOT = Path(__file__).resolve().parents[2]
ASSET_SET = ROOT / "evidence" / "p8_x0" / "reference-asset-set.v1.json"
REQUEST_SET = ROOT / "evidence" / "p8_b0" / "reference-asset-set-request.v1.json"
REQUEST_ROOT = ROOT / "evidence" / "p8_b0"
REFERENCE = ROOT / "evidence" / "p8_b2" / "reference-asset-set-consistency.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _payloads(request_set: dict[str, object]) -> dict[str, object]:
    raw_members = request_set.get("members")
    if type(raw_members) is not list:
        raise SystemExit("request manifest members malformed")
    payloads: dict[str, object] = {}
    for raw in cast(list[object], raw_members):
        if type(raw) is not dict:
            raise SystemExit("request manifest member malformed")
        ref = cast(dict[str, object], raw).get("request_ref")
        if type(ref) is not str:
            raise SystemExit("request_ref malformed")
        payloads[ref] = _json(REQUEST_ROOT / ref)
    return payloads


def main() -> None:
    asset_set = _json(ASSET_SET)
    request_set = _json(REQUEST_SET)
    payloads = _payloads(request_set)
    retained = _json(REFERENCE)

    derived = build_asset_set_consistency(request_set, asset_set, payloads)
    if derived != retained:
        raise SystemExit("retained P8-B2 consistency fixture drifted from deterministic projection")
    validate_asset_set_consistency(retained, request_set, asset_set, payloads)

    style = retained.get("style_profile")
    if type(style) is not dict or style.get("kind") != "style":
        raise SystemExit("P8-B2 must retain one exact cross-asset style profile")
    if retained.get("palette_profile") is not None:
        raise SystemExit("reference set intentionally exercises the no-shared-palette path")
    if retained.get("visual_style_policy") != "perceptual-evidence-required":
        raise SystemExit("style appearance must not be promoted to deterministic truth")
    if retained.get("visual_palette_policy") != "perceptual-evidence-required":
        raise SystemExit("palette appearance must not be promoted to deterministic truth")

    tampered = deepcopy(retained)
    tampered["visual_style_policy"] = "deterministic-pass"
    try:
        validate_asset_set_consistency(tampered, request_set, asset_set, payloads)
    except AssetSetConsistencyValidationError as exc:
        if exc.code != "consistency_contract_mismatch":
            raise SystemExit(f"unexpected tamper rejection: {exc.code}") from exc
    else:
        raise SystemExit("tampered visual-style authority must fail closed")

    core_lane = _json(CORE_LANE)
    if core_lane.get("current_child") != "P8-B3":
        raise SystemExit("P8-B2 checkpoint expects the merge handoff to P8-B3")

    print(
        json.dumps(
            {
                "schema": "tracepixel.p8-b2-checkpoint.v1",
                "member_count": len(cast(list[object], retained["members"])),
                "style_profile_id": style.get("profile_id"),
                "palette_profile": None,
                "profile_binding": "exact-digest-request-binding",
                "visual_style_policy": "perceptual-evidence-required",
                "visual_palette_policy": "perceptual-evidence-required",
                "provider_calls_added": 0,
                "raster_authority_added": False,
                "next_child": "P8-B3",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
