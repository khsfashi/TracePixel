from __future__ import annotations

from hashlib import sha256
import json
import math
import re
from typing import cast

from .humanoid_profile import (
    HUMANOID_PROFILE_SCHEMA_V1,
    HUMANOID_REQUIRED_CATEGORIES_V1,
    MAX_HUMANOID_EQUIPMENT_ANCHORS_V1,
    MAX_HUMANOID_IDENTITY_FEATURES_V1,
    MAX_HUMANOID_LANDMARKS_V1,
    MAX_HUMANOID_PROFILE_FACTS_V1,
    MAX_HUMANOID_PROFILE_SOURCES_V1,
    MAX_HUMANOID_PROFILE_UNKNOWNS_V1,
    MAX_HUMANOID_PROPORTIONS_V1,
    HumanoidProfileRefV1,
    HumanoidProfileV1,
)

_PROFILE_FIELDS = frozenset(("schema", "profile_id", "subject_label", "identity", "source_evidence", "observed_facts", "unknowns", "landmarks", "category_declarations", "proportion_constraints", "identity_features", "support_landmark_ids", "equipment_anchors", "stylization_tolerance"))
_REF_FIELDS = frozenset(("profile_id", "profile_schema", "sha256"))
_IDENTITY_FIELDS = frozenset(("family_id", "archetype_id", "form_id"))
_SOURCE_FIELDS = frozenset(("source_id", "kind", "locator", "title", "retrieved_at_utc"))
_FACT_FIELDS = frozenset(("fact_id", "text", "source_ids"))
_UNKNOWN_FIELDS = frozenset(("unknown_id", "text"))
_LANDMARK_FIELDS = frozenset(("landmark_id", "label", "parent_landmark_id", "mirror_landmark_id", "side"))
_CATEGORY_FIELDS = frozenset(("category", "status", "rationale", "unknown_id"))
_PROPORTION_FIELDS = frozenset(("constraint_id", "mode", "landmark_ids", "ratio_range", "text", "basis_fact_ids", "confidence"))
_RANGE_FIELDS = frozenset(("minimum", "maximum"))
_FEATURE_FIELDS = frozenset(("feature_id", "kind", "landmark_ids", "text", "basis_fact_ids", "confidence"))
_ANCHOR_FIELDS = frozenset(("anchor_id", "landmark_id", "side", "attachment_class", "basis_fact_ids", "confidence"))
_STYLIZATION_FIELDS = frozenset(("minimum_feature_pixels", "maximum_exaggeration_pixels", "basis_fact_ids", "confidence"))
_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_CONFIDENCE = frozenset(("low", "medium", "high"))
_MODES = frozenset(("required-range", "hint", "stylization-tolerance"))
_SIDES = frozenset(("center", "left", "right"))
_FEATURE_KINDS = frozenset(("head-face-hair", "silhouette-critical"))
_REQUIRED_CATEGORIES = frozenset(HUMANOID_REQUIRED_CATEGORIES_V1)


class HumanoidProfileValidationError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise HumanoidProfileValidationError(code, path, message)


def _object(value: object, path: str, fields: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    obj = cast(dict[object, object], value)
    if not all(type(key) is str for key in obj):
        _fail("invalid_fields", path, "object keys must be strings")
    actual = frozenset(cast(dict[str, object], obj))
    if actual != fields:
        _fail("invalid_fields", path, f"expected fields {sorted(fields)}, got {sorted(actual)}")
    return cast(dict[str, object], obj)


def _slug(value: object, path: str) -> str:
    if type(value) is not str or _SLUG.fullmatch(value) is None:
        _fail("invalid_id", path, "must be a lowercase ASCII slug of length 1..64")
    return value


def _text(value: object, path: str, maximum: int) -> str:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        _fail("invalid_text", path, f"must be a non-empty string of length <= {maximum}")
    return value


def _finite(value: object, path: str) -> float:
    if type(value) not in (int, float):
        _fail("invalid_type", path, "must be a JSON number")
    parsed = float(value)
    if not math.isfinite(parsed):
        _fail("invalid_range", path, "must be finite")
    return parsed


def _ids(value: object, path: str, maximum: int) -> list[str]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    raw = cast(list[object], value)
    if not 1 <= len(raw) <= maximum:
        _fail("invalid_count", path, f"count must be in [1, {maximum}]")
    result = [_slug(item, f"{path}[{index}]") for index, item in enumerate(raw)]
    if len(result) != len(set(result)):
        _fail("duplicate_reference", path, "references must be unique")
    return result


def _fact_refs(value: object, path: str, fact_ids: set[str]) -> list[str]:
    refs = _ids(value, path, MAX_HUMANOID_PROFILE_FACTS_V1)
    missing = [item for item in refs if item not in fact_ids]
    if missing:
        _fail("unknown_fact_reference", path, f"unknown fact ids {missing}")
    return refs


def validate_humanoid_profile(value: object) -> HumanoidProfileV1:
    root = _object(value, "$", _PROFILE_FIELDS)
    if root["schema"] != HUMANOID_PROFILE_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {HUMANOID_PROFILE_SCHEMA_V1!r}")
    _slug(root["profile_id"], "$.profile_id")
    _text(root["subject_label"], "$.subject_label", 128)

    identity = _object(root["identity"], "$.identity", _IDENTITY_FIELDS)
    for key in ("family_id", "archetype_id", "form_id"):
        _slug(identity[key], f"$.identity.{key}")

    sources_raw = root["source_evidence"]
    if type(sources_raw) is not list or not 1 <= len(sources_raw) <= MAX_HUMANOID_PROFILE_SOURCES_V1:
        _fail("invalid_source_count", "$.source_evidence", f"count must be in [1, {MAX_HUMANOID_PROFILE_SOURCES_V1}]")
    source_ids: set[str] = set()
    for index, raw in enumerate(cast(list[object], sources_raw)):
        path = f"$.source_evidence[{index}]"
        source = _object(raw, path, _SOURCE_FIELDS)
        source_id = _slug(source["source_id"], f"{path}.source_id")
        if source_id in source_ids:
            _fail("duplicate_source", f"{path}.source_id", "source id must be unique")
        source_ids.add(source_id)
        _slug(source["kind"], f"{path}.kind")
        _text(source["locator"], f"{path}.locator", 1024)
        _text(source["title"], f"{path}.title", 256)
        retrieved = source["retrieved_at_utc"]
        if type(retrieved) is not str or _UTC.fullmatch(retrieved) is None:
            _fail("invalid_retrieved_at", f"{path}.retrieved_at_utc", "must be UTC YYYY-MM-DDTHH:MM:SSZ")

    facts_raw = root["observed_facts"]
    if type(facts_raw) is not list or not 1 <= len(facts_raw) <= MAX_HUMANOID_PROFILE_FACTS_V1:
        _fail("invalid_fact_count", "$.observed_facts", f"count must be in [1, {MAX_HUMANOID_PROFILE_FACTS_V1}]")
    fact_ids: set[str] = set()
    for index, raw in enumerate(cast(list[object], facts_raw)):
        path = f"$.observed_facts[{index}]"
        fact = _object(raw, path, _FACT_FIELDS)
        fact_id = _slug(fact["fact_id"], f"{path}.fact_id")
        if fact_id in fact_ids:
            _fail("duplicate_fact", f"{path}.fact_id", "fact id must be unique")
        fact_ids.add(fact_id)
        _text(fact["text"], f"{path}.text", 512)
        refs = _ids(fact["source_ids"], f"{path}.source_ids", MAX_HUMANOID_PROFILE_SOURCES_V1)
        if any(item not in source_ids for item in refs):
            _fail("unknown_source_reference", f"{path}.source_ids", "all source ids must exist")

    unknowns_raw = root["unknowns"]
    if type(unknowns_raw) is not list or len(unknowns_raw) > MAX_HUMANOID_PROFILE_UNKNOWNS_V1:
        _fail("invalid_unknown_count", "$.unknowns", f"count must be <= {MAX_HUMANOID_PROFILE_UNKNOWNS_V1}")
    unknown_ids: set[str] = set()
    for index, raw in enumerate(cast(list[object], unknowns_raw)):
        path = f"$.unknowns[{index}]"
        unknown = _object(raw, path, _UNKNOWN_FIELDS)
        unknown_id = _slug(unknown["unknown_id"], f"{path}.unknown_id")
        if unknown_id in unknown_ids:
            _fail("duplicate_unknown", f"{path}.unknown_id", "unknown id must be unique")
        unknown_ids.add(unknown_id)
        _text(unknown["text"], f"{path}.text", 512)

    landmarks_raw = root["landmarks"]
    if type(landmarks_raw) is not list or not 1 <= len(landmarks_raw) <= MAX_HUMANOID_LANDMARKS_V1:
        _fail("invalid_landmark_count", "$.landmarks", f"count must be in [1, {MAX_HUMANOID_LANDMARKS_V1}]")
    landmarks: dict[str, tuple[str | None, str | None, str, str]] = {}
    for index, raw in enumerate(cast(list[object], landmarks_raw)):
        path = f"$.landmarks[{index}]"
        landmark = _object(raw, path, _LANDMARK_FIELDS)
        landmark_id = _slug(landmark["landmark_id"], f"{path}.landmark_id")
        if landmark_id in landmarks:
            _fail("duplicate_landmark", f"{path}.landmark_id", "landmark id must be unique")
        _text(landmark["label"], f"{path}.label", 128)
        parent = landmark["parent_landmark_id"]
        mirror = landmark["mirror_landmark_id"]
        parent_id = None if parent is None else _slug(parent, f"{path}.parent_landmark_id")
        mirror_id = None if mirror is None else _slug(mirror, f"{path}.mirror_landmark_id")
        side = landmark["side"]
        if type(side) is not str or side not in _SIDES:
            _fail("invalid_side", f"{path}.side", f"must be one of {sorted(_SIDES)}")
        if parent_id == landmark_id or mirror_id == landmark_id:
            _fail("self_landmark_reference", path, "landmark cannot reference itself")
        landmarks[landmark_id] = (parent_id, mirror_id, cast(str, side), path)

    for landmark_id, (parent, mirror, side, path) in landmarks.items():
        if parent is not None and parent not in landmarks:
            _fail("unknown_landmark_reference", f"{path}.parent_landmark_id", f"unknown landmark {parent!r}")
        if mirror is not None:
            if mirror not in landmarks:
                _fail("unknown_landmark_reference", f"{path}.mirror_landmark_id", f"unknown landmark {mirror!r}")
            peer = landmarks[mirror]
            if peer[1] != landmark_id:
                _fail("nonreciprocal_mirror", f"{path}.mirror_landmark_id", "mirror relationship must be reciprocal")
            if side == "center" or peer[2] == side:
                _fail("invalid_mirror_side", f"{path}.side", "mirrored landmarks must use opposite left/right sides")
        elif side != "center":
            _fail("missing_mirror_landmark", f"{path}.mirror_landmark_id", "left/right landmarks require a reciprocal mirror")

    for landmark_id in landmarks:
        seen: set[str] = set()
        current: str | None = landmark_id
        while current is not None:
            if current in seen:
                _fail("landmark_parent_cycle", "$.landmarks", f"parent cycle includes {current!r}")
            seen.add(current)
            current = landmarks[current][0]

    declarations_raw = root["category_declarations"]
    if type(declarations_raw) is not list or len(declarations_raw) != len(HUMANOID_REQUIRED_CATEGORIES_V1):
        _fail("invalid_category_count", "$.category_declarations", f"must contain exactly {len(HUMANOID_REQUIRED_CATEGORIES_V1)} categories")
    declared: set[str] = set()
    for index, raw in enumerate(cast(list[object], declarations_raw)):
        path = f"$.category_declarations[{index}]"
        declaration = _object(raw, path, _CATEGORY_FIELDS)
        category = declaration["category"]
        if type(category) is not str or category not in _REQUIRED_CATEGORIES:
            _fail("invalid_category", f"{path}.category", "category is not part of the frozen G8-H0 set")
        if category in declared:
            _fail("duplicate_category", f"{path}.category", "category must be unique")
        declared.add(category)
        status = declaration["status"]
        if status not in ("constrained", "unknown"):
            _fail("invalid_category_status", f"{path}.status", "must be constrained or unknown")
        _text(declaration["rationale"], f"{path}.rationale", 512)
        unknown_id = declaration["unknown_id"]
        if status == "unknown":
            parsed = _slug(unknown_id, f"{path}.unknown_id")
            if parsed not in unknown_ids:
                _fail("unknown_unknown_reference", f"{path}.unknown_id", "must reference a declared unknown")
        elif unknown_id is not None:
            _fail("invalid_category_state", f"{path}.unknown_id", "must be null when constrained")
    if declared != _REQUIRED_CATEGORIES:
        _fail("missing_category", "$.category_declarations", "all frozen G8-H0 categories must be present")

    proportions_raw = root["proportion_constraints"]
    if type(proportions_raw) is not list or not 1 <= len(proportions_raw) <= MAX_HUMANOID_PROPORTIONS_V1:
        _fail("invalid_proportion_count", "$.proportion_constraints", f"count must be in [1, {MAX_HUMANOID_PROPORTIONS_V1}]")
    proportion_ids: set[str] = set()
    for index, raw in enumerate(cast(list[object], proportions_raw)):
        path = f"$.proportion_constraints[{index}]"
        constraint = _object(raw, path, _PROPORTION_FIELDS)
        constraint_id = _slug(constraint["constraint_id"], f"{path}.constraint_id")
        if constraint_id in proportion_ids:
            _fail("duplicate_proportion", f"{path}.constraint_id", "constraint id must be unique")
        proportion_ids.add(constraint_id)
        mode = constraint["mode"]
        if type(mode) is not str or mode not in _MODES:
            _fail("invalid_constraint_mode", f"{path}.mode", f"must be one of {sorted(_MODES)}")
        landmark_refs = _ids(constraint["landmark_ids"], f"{path}.landmark_ids", MAX_HUMANOID_LANDMARKS_V1)
        if len(landmark_refs) < 2 or any(item not in landmarks for item in landmark_refs):
            _fail("unknown_landmark_reference", f"{path}.landmark_ids", "proportions require at least two known landmarks")
        ratio = _object(constraint["ratio_range"], f"{path}.ratio_range", _RANGE_FIELDS)
        minimum = _finite(ratio["minimum"], f"{path}.ratio_range.minimum")
        maximum = _finite(ratio["maximum"], f"{path}.ratio_range.maximum")
        if minimum < 0 or maximum > 64 or minimum > maximum:
            _fail("invalid_range", f"{path}.ratio_range", "ratio range must be ordered inside [0, 64]")
        _text(constraint["text"], f"{path}.text", 512)
        _fact_refs(constraint["basis_fact_ids"], f"{path}.basis_fact_ids", fact_ids)
        if constraint["confidence"] not in _CONFIDENCE:
            _fail("invalid_confidence", f"{path}.confidence", f"must be one of {sorted(_CONFIDENCE)}")

    features_raw = root["identity_features"]
    if type(features_raw) is not list or not 1 <= len(features_raw) <= MAX_HUMANOID_IDENTITY_FEATURES_V1:
        _fail("invalid_identity_feature_count", "$.identity_features", f"count must be in [1, {MAX_HUMANOID_IDENTITY_FEATURES_V1}]")
    feature_kinds: set[str] = set()
    feature_ids: set[str] = set()
    for index, raw in enumerate(cast(list[object], features_raw)):
        path = f"$.identity_features[{index}]"
        feature = _object(raw, path, _FEATURE_FIELDS)
        feature_id = _slug(feature["feature_id"], f"{path}.feature_id")
        if feature_id in feature_ids:
            _fail("duplicate_identity_feature", f"{path}.feature_id", "feature id must be unique")
        feature_ids.add(feature_id)
        kind = feature["kind"]
        if type(kind) is not str or kind not in _FEATURE_KINDS:
            _fail("invalid_identity_feature_kind", f"{path}.kind", f"must be one of {sorted(_FEATURE_KINDS)}")
        feature_kinds.add(kind)
        refs = _ids(feature["landmark_ids"], f"{path}.landmark_ids", MAX_HUMANOID_LANDMARKS_V1)
        if any(item not in landmarks for item in refs):
            _fail("unknown_landmark_reference", f"{path}.landmark_ids", "identity features must reference known landmarks")
        _text(feature["text"], f"{path}.text", 512)
        _fact_refs(feature["basis_fact_ids"], f"{path}.basis_fact_ids", fact_ids)
        if feature["confidence"] not in _CONFIDENCE:
            _fail("invalid_confidence", f"{path}.confidence", f"must be one of {sorted(_CONFIDENCE)}")
    if feature_kinds != _FEATURE_KINDS:
        _fail("missing_identity_feature_kind", "$.identity_features", "head/face/hair and silhouette-critical identity features are both required")

    support_refs = _ids(root["support_landmark_ids"], "$.support_landmark_ids", MAX_HUMANOID_LANDMARKS_V1)
    if any(item not in landmarks for item in support_refs):
        _fail("unknown_landmark_reference", "$.support_landmark_ids", "support landmarks must exist")

    anchors_raw = root["equipment_anchors"]
    if type(anchors_raw) is not list or not 1 <= len(anchors_raw) <= MAX_HUMANOID_EQUIPMENT_ANCHORS_V1:
        _fail("invalid_equipment_anchor_count", "$.equipment_anchors", f"count must be in [1, {MAX_HUMANOID_EQUIPMENT_ANCHORS_V1}]")
    anchor_ids: set[str] = set()
    for index, raw in enumerate(cast(list[object], anchors_raw)):
        path = f"$.equipment_anchors[{index}]"
        anchor = _object(raw, path, _ANCHOR_FIELDS)
        anchor_id = _slug(anchor["anchor_id"], f"{path}.anchor_id")
        if anchor_id in anchor_ids:
            _fail("duplicate_equipment_anchor", f"{path}.anchor_id", "anchor id must be unique")
        anchor_ids.add(anchor_id)
        landmark_id = _slug(anchor["landmark_id"], f"{path}.landmark_id")
        if landmark_id not in landmarks:
            _fail("unknown_landmark_reference", f"{path}.landmark_id", "anchor landmark must exist")
        side = anchor["side"]
        if type(side) is not str or side not in _SIDES or side != landmarks[landmark_id][2]:
            _fail("anchor_side_mismatch", f"{path}.side", "anchor side must match its landmark side")
        _slug(anchor["attachment_class"], f"{path}.attachment_class")
        _fact_refs(anchor["basis_fact_ids"], f"{path}.basis_fact_ids", fact_ids)
        if anchor["confidence"] not in _CONFIDENCE:
            _fail("invalid_confidence", f"{path}.confidence", f"must be one of {sorted(_CONFIDENCE)}")

    stylization = _object(root["stylization_tolerance"], "$.stylization_tolerance", _STYLIZATION_FIELDS)
    minimum_pixels = stylization["minimum_feature_pixels"]
    maximum_exaggeration = stylization["maximum_exaggeration_pixels"]
    if type(minimum_pixels) is not int or not 1 <= minimum_pixels <= 64:
        _fail("invalid_stylization_range", "$.stylization_tolerance.minimum_feature_pixels", "must be an integer in [1, 64]")
    if type(maximum_exaggeration) is not int or not 0 <= maximum_exaggeration <= 16:
        _fail("invalid_stylization_range", "$.stylization_tolerance.maximum_exaggeration_pixels", "must be an integer in [0, 16]")
    _fact_refs(stylization["basis_fact_ids"], "$.stylization_tolerance.basis_fact_ids", fact_ids)
    if stylization["confidence"] not in _CONFIDENCE:
        _fail("invalid_confidence", "$.stylization_tolerance.confidence", f"must be one of {sorted(_CONFIDENCE)}")

    return cast(HumanoidProfileV1, value)


def humanoid_profile_sha256(value: object) -> str:
    validated = validate_humanoid_profile(value)
    canonical = json.dumps(validated, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return sha256(canonical).hexdigest()


def validate_humanoid_profile_reference(value: object, profile: object) -> HumanoidProfileRefV1:
    ref = _object(value, "$ref", _REF_FIELDS)
    validated = validate_humanoid_profile(profile)
    if ref["profile_id"] != validated["profile_id"]:
        _fail("profile_id_mismatch", "$ref.profile_id", "must match the retained profile id")
    if ref["profile_schema"] != HUMANOID_PROFILE_SCHEMA_V1:
        _fail("invalid_profile_schema", "$ref.profile_schema", f"must equal {HUMANOID_PROFILE_SCHEMA_V1!r}")
    digest = ref["sha256"]
    if type(digest) is not str or _SHA256.fullmatch(digest) is None:
        _fail("invalid_digest", "$ref.sha256", "must be 64 lowercase hexadecimal characters")
    expected = humanoid_profile_sha256(validated)
    if digest != expected:
        _fail("profile_digest_mismatch", "$ref.sha256", f"expected {expected}")
    return cast(HumanoidProfileRefV1, value)
