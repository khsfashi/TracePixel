from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tracepixel.model.research_profile_validation import (
    morphology_profile_sha256,
    validate_morphology_profile_reference,
    validate_simple_creature_morphology_profile,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "evidence" / "p10_c1" / "simple-creature-profile.v1.json"
PROFILE_REF = ROOT / "evidence" / "p10_c1" / "simple-creature-profile-ref.v1.json"
C0_CONTRACT = ROOT / "evidence" / "p10_c0" / "promotion-contract.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"

EXPECTED_CATEGORIES = {
    "relative-proportion",
    "symmetry-orientation",
    "articulation",
    "silhouette-critical",
    "support-contact",
    "resolution-stylization",
}


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"P10-C1 checkpoint failed: {message}")


def main() -> int:
    profile = _json(PROFILE)
    profile_ref = _json(PROFILE_REF)
    contract = _json(C0_CONTRACT)
    lane = _json(CORE_LANE)

    validated = validate_simple_creature_morphology_profile(profile)
    validate_morphology_profile_reference(profile_ref, validated)
    _expect(profile_ref.get("sha256") == morphology_profile_sha256(validated), "retained profile digest drifted")
    _expect(profile.get("schema") == "tracepixel.morphology-profile.v1", "morphology schema drifted")

    structure = cast(dict[str, object], profile.get("creature_structure"))
    subject = cast(dict[str, object], structure.get("subject"))
    _expect(all(type(subject.get(key)) is str for key in ("family_id", "species_id", "form_id")), "subject family/species/form identity is incomplete")

    landmarks = cast(list[object], structure.get("landmarks"))
    _expect(len(landmarks) >= 1, "canonical landmark set is empty")
    landmark_ids = [cast(dict[str, object], item).get("landmark_id") for item in landmarks]
    _expect(len(landmark_ids) == len(set(landmark_ids)), "landmark ids are not unique")

    declarations = cast(list[object], structure.get("category_declarations"))
    declared_categories = {
        cast(dict[str, object], item).get("category")
        for item in declarations
    }
    _expect(declared_categories == EXPECTED_CATEGORIES, "required morphology categories are not exactly declared")

    constraints = cast(list[object], structure.get("constraints"))
    modes = {cast(dict[str, object], item).get("mode") for item in constraints}
    _expect("required-range" in modes, "required-range constraint mode is not retained")
    _expect("hint" in modes, "hint constraint mode is not retained")
    _expect("stylization-tolerance" in modes, "stylization-tolerance constraint mode is not retained")

    morphology_contract = cast(dict[str, object], contract.get("morphology_profile"))
    _expect(morphology_contract.get("planned_schema") == profile.get("schema"), "C1 schema diverged from frozen C0 contract")
    _expect(morphology_contract.get("is_raster_authority") is False, "morphology profile widened into raster authority")

    _expect(lane.get("current") == "P10", "core lane is not P10")
    _expect(lane.get("current_child") == "P10-C1", "core lane is not P10-C1")
    _expect(lane.get("active_issue") == 109, "P10-C1 is not bound to issue #109")

    print(json.dumps({
        "schema": "tracepixel.p10-c1-checkpoint.v1",
        "status": "pass",
        "source_issue": 109,
        "current_child": "P10-C1",
        "next_child": "P10-C2",
        "profile_schema": profile["schema"],
        "profile_sha256": profile_ref["sha256"],
        "constraint_categories": len(EXPECTED_CATEGORIES),
        "provider_calls": 0,
        "raster_generation": 0,
        "raster_authority_added": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
