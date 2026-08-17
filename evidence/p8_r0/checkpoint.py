from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tracepixel.model.research_profile_validation import (
    morphology_profile_sha256,
    validate_form_resolution,
    validate_morphology_profile,
    validate_morphology_profile_reference,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "evidence" / "p8_r0" / "reference-morphology-profile.v1.json"
KNOWN = ROOT / "evidence" / "p8_r0" / "reference-known-resolution.v1.json"
RESEARCH = ROOT / "evidence" / "p8_r0" / "reference-research-required.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"
EXPECTED_PROFILE_SHA256 = "39c6c991724a2e18530343f8a65943779d2773f26e7f437a32c9c0b24b289adc"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _validate_lane(lane: dict[str, object]) -> None:
    if lane.get("current") != "P8" or lane.get("active_issue") != 92:
        raise SystemExit("P8-R0 checkpoint requires live P8 / issue #92")
    children = lane.get("child_sequences")
    if type(children) is not dict:
        raise SystemExit("core lane child_sequences malformed")
    p8 = cast(dict[str, object], children).get("P8")
    child = lane.get("current_child")
    if type(p8) is not list or child not in cast(list[object], p8):
        raise SystemExit("active P8 child is not declared")
    names = cast(list[str], p8)
    if "P8-R0" not in names or names.index(cast(str, child)) < names.index("P8-R0"):
        raise SystemExit("core lane regressed before P8-R0")


def main() -> int:
    profile = validate_morphology_profile(_json(PROFILE))
    known = validate_form_resolution(_json(KNOWN))
    research = validate_form_resolution(_json(RESEARCH))
    lane = _json(CORE_LANE)
    _validate_lane(lane)

    digest = morphology_profile_sha256(profile)
    if digest != EXPECTED_PROFILE_SHA256:
        raise SystemExit("reference morphology profile digest drifted")
    ref = known["profile_ref"]
    if ref is None:
        raise SystemExit("known resolution lost profile reference")
    validate_morphology_profile_reference(ref, profile)
    if research["resolution"] != "research_required" or research["research_request"] is None:
        raise SystemExit("research-required fixture drifted")

    print(
        json.dumps(
            {
                "schema": "tracepixel.p8-r0-checkpoint.v1",
                "profile_id": profile["profile_id"],
                "profile_sha256": digest,
                "source_count": len(profile["source_evidence"]),
                "observed_fact_count": len(profile["observed_facts"]),
                "inferred_constraint_count": len(profile["inferred_constraints"]),
                "artistic_convention_count": len(profile["artistic_conventions"]),
                "unknown_count": len(profile["unknowns"]),
                "known_profile_resolution_valid": True,
                "research_required_resolution_valid": True,
                "network_invoked": False,
                "provider_invoked": False,
                "raster_authority_created": False,
                "next": "P8-B0",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
