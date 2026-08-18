from __future__ import annotations

from hashlib import sha256
import json
import math
import re
from typing import cast

from .creature_pose import (
    CREATURE_POSE_SCHEMA_V1,
    MAX_POSE_RELATIONS_V1,
    CreaturePoseRefV1,
    CreaturePoseV1,
)
from .research_profile import MAX_PROFILE_LANDMARKS_V1, MorphologyProfileV1
from .research_profile_validation import (
    ResearchProfileValidationError,
    validate_morphology_profile_reference,
    validate_simple_creature_morphology_profile,
)

_ROOT_FIELDS = frozenset(("schema", "pose_id", "pose_name", "morphology_ref", "orientation_intent", "relations"))
_ORIENTATION_FIELDS = frozenset(("facing", "description"))
_RELATION_FIELDS = frozenset(("relation_id", "kind", "mode", "landmark_ids", "value_range", "morphology_constraint_ids", "text"))
_RANGE_FIELDS = frozenset(("minimum", "maximum", "unit"))
_POSE_REF_FIELDS = frozenset(("pose_id", "pose_schema", "sha256"))
_FACINGS = frozenset(("left", "right", "front", "rear", "three-quarter-left", "three-quarter-right"))
_RELATION_KINDS = frozenset(("landmark-relation", "articulation", "support-contact", "silhouette-facing"))
_MODES = frozenset(("required-range", "hint", "stylization-tolerance"))
_RANGE_UNITS = frozenset(("ratio", "degrees", "pixels"))
_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_RELATION_KINDS = frozenset(("articulation", "support-contact", "silhouette-facing"))
_ALLOWED_BASIS_CATEGORIES = {
    "landmark-relation": frozenset(("relative-proportion", "symmetry-orientation", "articulation", "resolution-stylization")),
    "articulation": frozenset(("articulation",)),
    "support-contact": frozenset(("support-contact",)),
    "silhouette-facing": frozenset(("silhouette-critical",)),
}


class CreaturePoseValidationError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise CreaturePoseValidationError(code, path, message)


def _object(value: object, path: str, fields: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    obj = cast(dict[object, object], value)
    if not all(type(key) is str for key in obj):
        _fail("invalid_fields", path, "object keys must be strings")
    actual = frozenset(cast(dict[str, object], obj))
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail("invalid_fields", path, "; ".join(parts))
    return cast(dict[str, object], obj)


def _slug(value: object, path: str) -> str:
    if type(value) is not str or _SLUG.fullmatch(value) is None:
        _fail("invalid_id", path, "must be a lowercase ASCII slug of length 1..64")
    return value


def _text(value: object, path: str, *, maximum: int) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    if not 1 <= len(value) <= maximum:
        _fail("invalid_value", path, f"length must be in [1, {maximum}]")
    return value


def _ids(value: object, path: str, *, maximum: int) -> list[str]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    raw = cast(list[object], value)
    if not 1 <= len(raw) <= maximum:
        _fail("invalid_count", path, f"item count must be in [1, {maximum}]")
    parsed = [_slug(item, f"{path}[{index}]") for index, item in enumerate(raw)]
    if len(set(parsed)) != len(parsed):
        _fail("duplicate_reference", path, "references must be unique")
    return parsed


def _finite_range(value: object, path: str) -> tuple[float, float, str]:
    bounds = _object(value, path, _RANGE_FIELDS)
    numbers: list[float] = []
    for field in ("minimum", "maximum"):
        raw = bounds[field]
        if type(raw) not in (int, float):
            _fail("invalid_type", f"{path}.{field}", "must be an exact JSON number")
        number = float(raw)
        if not math.isfinite(number):
            _fail("invalid_value", f"{path}.{field}", "must be finite")
        numbers.append(number)
    minimum, maximum = numbers
    if minimum > maximum:
        _fail("invalid_range", path, "minimum must be <= maximum")
    unit = bounds["unit"]
    if type(unit) is not str or unit not in _RANGE_UNITS:
        _fail("invalid_range_unit", f"{path}.unit", f"must be one of {sorted(_RANGE_UNITS)}")
    if unit == "ratio" and (minimum < 0 or maximum > 64):
        _fail("invalid_range", path, "ratio range must stay within [0, 64]")
    if unit == "degrees" and (minimum < -360 or maximum > 360):
        _fail("invalid_range", path, "degree range must stay within [-360, 360]")
    if unit == "pixels" and (minimum < 0 or maximum > 4096):
        _fail("invalid_range", path, "pixel range must stay within [0, 4096]")
    return minimum, maximum, unit


def _profile_structure(profile: MorphologyProfileV1) -> tuple[set[str], dict[str, dict[str, object]]]:
    structure = cast(dict[str, object], profile["creature_structure"])
    landmarks = cast(list[object], structure["landmarks"])
    landmark_ids = {
        cast(str, cast(dict[str, object], landmark)["landmark_id"])
        for landmark in landmarks
    }
    constraints = cast(list[object], structure["constraints"])
    by_id = {
        cast(str, cast(dict[str, object], constraint)["constraint_id"]): cast(dict[str, object], constraint)
        for constraint in constraints
    }
    return landmark_ids, by_id


def validate_creature_pose(value: object, morphology_profile: object) -> CreaturePoseV1:
    try:
        profile = validate_simple_creature_morphology_profile(morphology_profile)
    except ResearchProfileValidationError as exc:
        _fail("invalid_morphology_profile", "$morphology", str(exc))
    root = _object(value, "$", _ROOT_FIELDS)
    if root["schema"] != CREATURE_POSE_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {CREATURE_POSE_SCHEMA_V1!r}")
    _slug(root["pose_id"], "$.pose_id")
    _text(root["pose_name"], "$.pose_name", maximum=128)
    try:
        validate_morphology_profile_reference(root["morphology_ref"], profile)
    except ResearchProfileValidationError as exc:
        _fail("morphology_binding_mismatch", "$.morphology_ref", str(exc))

    orientation = _object(root["orientation_intent"], "$.orientation_intent", _ORIENTATION_FIELDS)
    facing = orientation["facing"]
    if type(facing) is not str or facing not in _FACINGS:
        _fail("invalid_facing", "$.orientation_intent.facing", f"must be one of {sorted(_FACINGS)}")
    _text(orientation["description"], "$.orientation_intent.description", maximum=512)

    landmark_ids, morphology_constraints = _profile_structure(profile)
    relations_raw = root["relations"]
    if type(relations_raw) is not list:
        _fail("invalid_type", "$.relations", "must be a JSON array")
    relations = cast(list[object], relations_raw)
    if not 1 <= len(relations) <= MAX_POSE_RELATIONS_V1:
        _fail("invalid_relation_count", "$.relations", f"count must be in [1, {MAX_POSE_RELATIONS_V1}]")

    relation_ids: set[str] = set()
    seen_kinds: set[str] = set()
    for index, raw in enumerate(relations):
        path = f"$.relations[{index}]"
        relation = _object(raw, path, _RELATION_FIELDS)
        relation_id = _slug(relation["relation_id"], f"{path}.relation_id")
        if relation_id in relation_ids:
            _fail("duplicate_relation", f"{path}.relation_id", f"duplicate relation id {relation_id!r}")
        relation_ids.add(relation_id)

        kind = relation["kind"]
        if type(kind) is not str or kind not in _RELATION_KINDS:
            _fail("invalid_relation_kind", f"{path}.kind", f"must be one of {sorted(_RELATION_KINDS)}")
        seen_kinds.add(kind)

        mode = relation["mode"]
        if type(mode) is not str or mode not in _MODES:
            _fail("invalid_constraint_mode", f"{path}.mode", f"must be one of {sorted(_MODES)}")

        relation_landmarks = _ids(relation["landmark_ids"], f"{path}.landmark_ids", maximum=MAX_PROFILE_LANDMARKS_V1)
        missing_landmarks = [item for item in relation_landmarks if item not in landmark_ids]
        if missing_landmarks:
            _fail("unknown_landmark_reference", f"{path}.landmark_ids", f"unknown landmark ids {missing_landmarks}")

        basis_ids = _ids(relation["morphology_constraint_ids"], f"{path}.morphology_constraint_ids", maximum=MAX_POSE_RELATIONS_V1)
        missing_constraints = [item for item in basis_ids if item not in morphology_constraints]
        if missing_constraints:
            _fail("unknown_morphology_constraint_reference", f"{path}.morphology_constraint_ids", f"unknown morphology constraint ids {missing_constraints}")

        allowed_categories = _ALLOWED_BASIS_CATEGORIES[kind]
        basis_constraints = [morphology_constraints[item] for item in basis_ids]
        bad_categories = [
            cast(str, item["category"])
            for item in basis_constraints
            if item["category"] not in allowed_categories
        ]
        if bad_categories:
            _fail("incompatible_morphology_constraint", f"{path}.morphology_constraint_ids", f"{kind!r} cannot bind morphology categories {bad_categories}")
        covered_landmarks = {
            cast(str, landmark)
            for item in basis_constraints
            for landmark in cast(list[object], item["landmark_ids"])
        }
        uncovered = [item for item in relation_landmarks if item not in covered_landmarks]
        if uncovered:
            _fail("uncovered_pose_landmark", f"{path}.landmark_ids", f"pose landmarks are not covered by bound morphology constraints: {uncovered}")

        value_range = relation["value_range"]
        parsed_range: tuple[float, float, str] | None = None
        if value_range is not None:
            parsed_range = _finite_range(value_range, f"{path}.value_range")
        if mode in ("required-range", "stylization-tolerance") and parsed_range is None:
            _fail("range_required", f"{path}.value_range", f"mode {mode!r} requires a finite value range")
        if mode == "hint" and parsed_range is not None:
            _fail("range_for_hint", f"{path}.value_range", "hint relations must not carry a numeric range")

        if kind == "articulation":
            if mode != "required-range" or parsed_range is None:
                _fail("bounded_articulation_required", path, "articulation relations require a required-range degree bound")
            minimum, maximum, unit = parsed_range
            if unit != "degrees":
                _fail("invalid_range_unit", f"{path}.value_range.unit", "articulation relations require 'degrees'")
            morphology_ranges: list[tuple[float, float]] = []
            for constraint in basis_constraints:
                candidate = constraint["value_range"]
                if candidate is None:
                    continue
                raw_candidate = cast(dict[str, object], candidate)
                if raw_candidate.get("unit") != "degrees":
                    continue
                morphology_ranges.append((float(cast(float | int, raw_candidate["minimum"])), float(cast(float | int, raw_candidate["maximum"]))))
            if not any(bound_min <= minimum and maximum <= bound_max for bound_min, bound_max in morphology_ranges):
                _fail("articulation_outside_morphology", f"{path}.value_range", "pose articulation range must be contained by a bound morphology articulation range")
        elif kind == "landmark-relation" and parsed_range is not None:
            minimum, maximum, unit = parsed_range
            if mode == "stylization-tolerance" and unit != "pixels":
                _fail("invalid_range_unit", f"{path}.value_range.unit", "stylization-tolerance landmark relations require 'pixels'")
            morphology_ranges: list[tuple[float, float]] = []
            for constraint in basis_constraints:
                candidate = constraint["value_range"]
                if candidate is None:
                    continue
                raw_candidate = cast(dict[str, object], candidate)
                if raw_candidate.get("unit") != unit:
                    continue
                morphology_ranges.append((float(cast(float | int, raw_candidate["minimum"])), float(cast(float | int, raw_candidate["maximum"]))))
            if not any(bound_min <= minimum and maximum <= bound_max for bound_min, bound_max in morphology_ranges):
                _fail("relation_range_outside_morphology", f"{path}.value_range", "pose relation range must be contained by a bound morphology range with the same unit")
        elif kind in ("support-contact", "silhouette-facing"):
            if mode != "hint" or value_range is not None:
                _fail("invalid_relation_mode", path, f"{kind!r} is declarative in v1 and must use hint mode without a numeric range")

        _text(relation["text"], f"{path}.text", maximum=512)

    missing_kinds = sorted(_REQUIRED_RELATION_KINDS - seen_kinds)
    if missing_kinds:
        _fail("missing_required_relation", "$.relations", f"missing required relation kinds {missing_kinds}")

    return cast(CreaturePoseV1, value)


def creature_pose_canonical_bytes(pose: object, morphology_profile: object) -> bytes:
    validated = validate_creature_pose(pose, morphology_profile)
    return json.dumps(validated, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def creature_pose_sha256(pose: object, morphology_profile: object) -> str:
    return sha256(creature_pose_canonical_bytes(pose, morphology_profile)).hexdigest()


def validate_creature_pose_reference(ref: object, pose: object, morphology_profile: object) -> CreaturePoseRefV1:
    validated_ref = _object(ref, "$ref", _POSE_REF_FIELDS)
    pose_id = _slug(validated_ref["pose_id"], "$ref.pose_id")
    if validated_ref["pose_schema"] != CREATURE_POSE_SCHEMA_V1:
        _fail("invalid_pose_schema", "$ref.pose_schema", f"must equal {CREATURE_POSE_SCHEMA_V1!r}")
    digest = validated_ref["sha256"]
    if type(digest) is not str or _SHA256.fullmatch(digest) is None:
        _fail("invalid_digest", "$ref.sha256", "must be 64 lowercase hexadecimal characters")
    validated_pose = validate_creature_pose(pose, morphology_profile)
    if pose_id != validated_pose["pose_id"]:
        _fail("pose_id_mismatch", "$ref.pose_id", "reference pose_id does not match pose")
    if digest != creature_pose_sha256(validated_pose, morphology_profile):
        _fail("pose_digest_mismatch", "$ref.sha256", "reference digest does not match canonical pose bytes")
    return cast(CreaturePoseRefV1, ref)
