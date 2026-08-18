from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from evidence.g8_h0.forward_checkpoint import main as g8_h0_forward_main
from tracepixel.model.humanoid_profile import HUMANOID_REQUIRED_CATEGORIES_V1
from tracepixel.model.humanoid_profile_validation import (
    humanoid_profile_sha256,
    validate_humanoid_profile,
    validate_humanoid_profile_reference,
)

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "evidence" / "g8_h1" / "humanoid-profile.v1.json"
PROFILE_REF = ROOT / "evidence" / "g8_h1" / "humanoid-profile-ref.v1.json"
H0_CONTRACT = ROOT / "evidence" / "g8_h0" / "promotion-contract.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"G8-H1 checkpoint failed: {message}")


def main() -> int:
    _expect(g8_h0_forward_main() == 0, "G8-H0 historical checkpoint failed")

    profile = _json(PROFILE)
    profile_ref = _json(PROFILE_REF)
    contract = _json(H0_CONTRACT)
    lane = _json(CORE_LANE)

    validated = validate_humanoid_profile(profile)
    validate_humanoid_profile_reference(profile_ref, validated)
    _expect(profile_ref.get("sha256") == humanoid_profile_sha256(validated), "retained profile digest drifted")
    _expect(profile.get("schema") == "tracepixel.humanoid-profile.v1", "humanoid profile schema drifted")

    profile_contract = cast(dict[str, object], contract.get("anatomy_identity_profile"))
    _expect(profile_contract.get("planned_schema") == profile.get("schema"), "H1 schema diverged from frozen H0 contract")
    _expect(profile_contract.get("is_raster_authority") is False, "humanoid profile widened into raster authority")
    _expect(profile_contract.get("constraint_modes") == ["required-range", "hint", "stylization-tolerance"], "constraint modes drifted")

    declarations = cast(list[object], profile.get("category_declarations"))
    categories = {
        cast(dict[str, object], item).get("category")
        for item in declarations
    }
    _expect(categories == set(HUMANOID_REQUIRED_CATEGORIES_V1), "frozen H0 profile categories are not exactly represented")

    landmarks = cast(list[object], profile.get("landmarks"))
    _expect(len(landmarks) >= 7, "retained canonical humanoid landmark set is incomplete")
    landmark_ids = [cast(dict[str, object], item).get("landmark_id") for item in landmarks]
    _expect(len(landmark_ids) == len(set(landmark_ids)), "retained landmark ids are not unique")

    proportions = cast(list[object], profile.get("proportion_constraints"))
    _expect(any(cast(dict[str, object], item).get("mode") == "required-range" for item in proportions), "bounded required-range proportion is missing")

    features = cast(list[object], profile.get("identity_features"))
    kinds = {cast(dict[str, object], item).get("kind") for item in features}
    _expect(kinds == {"head-face-hair", "silhouette-critical"}, "identity-critical feature coverage is incomplete")

    supports = cast(list[object], profile.get("support_landmark_ids"))
    _expect(len(supports) >= 2, "static support/contact expectations are incomplete")
    anchors = cast(list[object], profile.get("equipment_anchors"))
    _expect(len(anchors) >= 1, "equipment anchor definitions are missing")

    scope = cast(dict[str, object], contract.get("scope"))
    _expect(scope.get("humanoid_provider_execution_allowed") is False, "H1 cannot authorize provider execution")
    _expect(scope.get("humanoid_raster_generation_allowed") is False, "H1 cannot authorize humanoid raster generation")
    _expect(scope.get("new_raster_authority_allowed") is False, "H1 cannot add raster authority")

    _expect(lane.get("current") == "G8", "core lane is not G8")
    _expect(lane.get("current_child") == "G8-H1", "core lane is not G8-H1")
    _expect(lane.get("active_issue") == 119, "G8-H1 is not bound to issue #119")
    children = cast(dict[str, object], lane.get("child_sequences"))
    g8 = cast(list[object], children.get("G8"))
    _expect(g8 == ["G8-H0", "G8-H1", "G8-H2", "G8-H3", "G8-H4", "G8-H5"], "G8 child sequence drifted")

    print(json.dumps({
        "schema": "tracepixel.g8-h1-checkpoint.v1",
        "status": "pass",
        "source_issue": 119,
        "current_child": "G8-H1",
        "next_child": "G8-H2",
        "profile_schema": profile["schema"],
        "profile_sha256": profile_ref["sha256"],
        "category_count": len(HUMANOID_REQUIRED_CATEGORIES_V1),
        "provider_calls": 0,
        "humanoid_raster_generation": 0,
        "raster_authority_added": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
