from __future__ import annotations

from hashlib import sha256
import json
import math
import re
from typing import cast

from .research_profile import (
    FORM_RESOLUTION_SCHEMA_V1,
    MAX_PROFILE_CATEGORY_DECLARATIONS_V1,
    MAX_PROFILE_CONSTRAINTS_V1,
    MAX_PROFILE_CONVENTIONS_V1,
    MAX_PROFILE_FACTS_V1,
    MAX_PROFILE_LANDMARKS_V1,
    MAX_PROFILE_STRUCTURAL_CONSTRAINTS_V1,
    MAX_PROFILE_UNKNOWNS_V1,
    MAX_RESEARCH_FETCH_CALLS_V1,
    MAX_RESEARCH_SEARCH_CALLS_V1,
    MAX_RESEARCH_SOURCE_KINDS_V1,
    MAX_RESEARCH_SOURCES_V1,
    MAX_RESEARCH_WALL_TIME_MS_V1,
    MORPHOLOGY_PROFILE_SCHEMA_V1,
    FormResolutionV1,
    MorphologyProfileRefV1,
    MorphologyProfileV1,
)

_FORM_FIELDS = frozenset(("schema", "form_id", "resolution", "profile_ref", "research_request"))
_PROFILE_REF_FIELDS = frozenset(("profile_id", "profile_schema", "sha256"))
_RESEARCH_REQUEST_FIELDS = frozenset(("goal", "allowed_source_kinds", "budget"))
_RESEARCH_BUDGET_FIELDS = frozenset(("max_sources", "max_search_calls", "max_fetch_calls", "max_wall_time_ms"))
_PROFILE_REQUIRED_FIELDS = frozenset(("schema", "profile_id", "subject_label", "source_evidence", "observed_facts", "inferred_constraints", "artistic_conventions", "unknowns"))
_PROFILE_OPTIONAL_FIELDS = frozenset(("creature_structure",))
_SOURCE_FIELDS = frozenset(("source_id", "kind", "locator", "title", "retrieved_at_utc"))
_FACT_FIELDS = frozenset(("fact_id", "text", "source_ids"))
_CONSTRAINT_FIELDS = frozenset(("constraint_id", "text", "basis_fact_ids", "confidence"))
_CONVENTION_FIELDS = frozenset(("convention_id", "text"))
_UNKNOWN_FIELDS = frozenset(("unknown_id", "text"))
_CREATURE_STRUCTURE_FIELDS = frozenset(("subject", "landmarks", "category_declarations", "constraints"))
_CREATURE_SUBJECT_FIELDS = frozenset(("family_id", "species_id", "form_id"))
_LANDMARK_FIELDS = frozenset(("landmark_id", "label", "parent_landmark_id", "mirror_landmark_id"))
_CATEGORY_DECLARATION_FIELDS = frozenset(("category", "status", "rationale", "unknown_id"))
_STRUCTURAL_CONSTRAINT_FIELDS = frozenset(("constraint_id", "category", "mode", "landmark_ids", "value_range", "text", "basis_fact_ids", "confidence"))
_VALUE_RANGE_FIELDS = frozenset(("minimum", "maximum", "unit"))
_SOURCE_KINDS = frozenset(("official", "academic", "museum", "encyclopedic", "manufacturer", "general_web"))
_CONFIDENCE_VALUES = frozenset(("low", "medium", "high"))
_CONSTRAINT_MODES = frozenset(("required-range", "hint", "stylization-tolerance"))
_CREATURE_CATEGORIES = (
    "relative-proportion",
    "symmetry-orientation",
    "articulation",
    "silhouette-critical",
    "support-contact",
    "resolution-stylization",
)
_CREATURE_CATEGORY_SET = frozenset(_CREATURE_CATEGORIES)
_CATEGORY_STATUS_VALUES = frozenset(("constrained", "not-applicable", "unknown"))
_ALWAYS_CONSTRAINED_CATEGORIES = frozenset((
    "relative-proportion",
    "silhouette-critical",
    "support-contact",
    "resolution-stylization",
))
_RANGE_UNITS = frozenset(("ratio", "degrees", "pixels"))
_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class ResearchProfileValidationError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise ResearchProfileValidationError(code, path, message)


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


def _profile_object(value: object, path: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    obj = cast(dict[object, object], value)
    if not all(type(key) is str for key in obj):
        _fail("invalid_fields", path, "object keys must be strings")
    actual = frozenset(cast(dict[str, object], obj))
    missing = _PROFILE_REQUIRED_FIELDS - actual
    extra = actual - (_PROFILE_REQUIRED_FIELDS | _PROFILE_OPTIONAL_FIELDS)
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f"missing {sorted(missing)}")
        if extra:
            parts.append(f"unexpected {sorted(extra)}")
        _fail("invalid_fields", path, "; ".join(parts))
    return cast(dict[str, object], obj)


def _slug(value: object, path: str) -> str:
    if type(value) is not str or _SLUG.fullmatch(value) is None:
        _fail("invalid_id", path, "must be a lowercase ASCII slug of length 1..64")
    return value


def _nullable_slug(value: object, path: str) -> str | None:
    if value is None:
        return None
    return _slug(value, path)


def _text(value: object, path: str, *, maximum: int) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    if not 1 <= len(value) <= maximum:
        _fail("invalid_value", path, f"length must be in [1, {maximum}]")
    return value


def _bounded_int(value: object, path: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        _fail("invalid_type", path, "must be an exact integer")
    if not minimum <= value <= maximum:
        _fail("invalid_value", path, f"must be in [{minimum}, {maximum}]")
    return value


def _finite_number(value: object, path: str) -> float:
    if type(value) not in (int, float):
        _fail("invalid_type", path, "must be an exact JSON number")
    parsed = float(value)
    if not math.isfinite(parsed):
        _fail("invalid_value", path, "must be finite")
    return parsed


def _string_ids(value: object, path: str, *, maximum: int) -> list[str]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    raw = cast(list[object], value)
    if not 1 <= len(raw) <= maximum:
        _fail("invalid_count", path, f"item count must be in [1, {maximum}]")
    out: list[str] = []
    for index, item in enumerate(raw):
        out.append(_slug(item, f"{path}[{index}]"))
    if len(set(out)) != len(out):
        _fail("duplicate_reference", path, "references must be unique")
    return out


def _profile_ref(value: object, path: str) -> MorphologyProfileRefV1:
    ref = _object(value, path, _PROFILE_REF_FIELDS)
    _slug(ref["profile_id"], f"{path}.profile_id")
    if ref["profile_schema"] != MORPHOLOGY_PROFILE_SCHEMA_V1:
        _fail("invalid_profile_schema", f"{path}.profile_schema", f"must equal {MORPHOLOGY_PROFILE_SCHEMA_V1!r}")
    digest = ref["sha256"]
    if type(digest) is not str or _SHA256.fullmatch(digest) is None:
        _fail("invalid_digest", f"{path}.sha256", "must be 64 lowercase hexadecimal characters")
    return cast(MorphologyProfileRefV1, value)


def validate_form_resolution(value: object) -> FormResolutionV1:
    root = _object(value, "$", _FORM_FIELDS)
    if root["schema"] != FORM_RESOLUTION_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {FORM_RESOLUTION_SCHEMA_V1!r}")
    _slug(root["form_id"], "$.form_id")
    resolution = root["resolution"]
    if resolution not in ("known_profile", "research_required"):
        _fail("invalid_resolution", "$.resolution", "must be 'known_profile' or 'research_required'")

    profile_ref = root["profile_ref"]
    request = root["research_request"]
    if resolution == "known_profile":
        if profile_ref is None or request is not None:
            _fail("invalid_resolution_state", "$", "known_profile requires profile_ref and forbids research_request")
        _profile_ref(profile_ref, "$.profile_ref")
    else:
        if profile_ref is not None or request is None:
            _fail("invalid_resolution_state", "$", "research_required requires research_request and forbids profile_ref")
        research = _object(request, "$.research_request", _RESEARCH_REQUEST_FIELDS)
        _text(research["goal"], "$.research_request.goal", maximum=512)
        kinds = research["allowed_source_kinds"]
        if type(kinds) is not list:
            _fail("invalid_type", "$.research_request.allowed_source_kinds", "must be a JSON array")
        raw_kinds = cast(list[object], kinds)
        if not 1 <= len(raw_kinds) <= MAX_RESEARCH_SOURCE_KINDS_V1:
            _fail("invalid_count", "$.research_request.allowed_source_kinds", f"count must be in [1, {MAX_RESEARCH_SOURCE_KINDS_V1}]")
        parsed_kinds: list[str] = []
        for index, kind in enumerate(raw_kinds):
            if type(kind) is not str or kind not in _SOURCE_KINDS:
                _fail("invalid_source_kind", f"$.research_request.allowed_source_kinds[{index}]", f"must be one of {sorted(_SOURCE_KINDS)}")
            parsed_kinds.append(kind)
        if len(set(parsed_kinds)) != len(parsed_kinds):
            _fail("duplicate_source_kind", "$.research_request.allowed_source_kinds", "source kinds must be unique")

        budget = _object(research["budget"], "$.research_request.budget", _RESEARCH_BUDGET_FIELDS)
        _bounded_int(budget["max_sources"], "$.research_request.budget.max_sources", minimum=1, maximum=MAX_RESEARCH_SOURCES_V1)
        _bounded_int(budget["max_search_calls"], "$.research_request.budget.max_search_calls", minimum=1, maximum=MAX_RESEARCH_SEARCH_CALLS_V1)
        _bounded_int(budget["max_fetch_calls"], "$.research_request.budget.max_fetch_calls", minimum=1, maximum=MAX_RESEARCH_FETCH_CALLS_V1)
        _bounded_int(budget["max_wall_time_ms"], "$.research_request.budget.max_wall_time_ms", minimum=1, maximum=MAX_RESEARCH_WALL_TIME_MS_V1)

    return cast(FormResolutionV1, value)


def _validate_creature_structure(
    value: object,
    *,
    fact_ids: set[str],
    unknown_ids: set[str],
) -> None:
    root = _object(value, "$.creature_structure", _CREATURE_STRUCTURE_FIELDS)
    subject = _object(root["subject"], "$.creature_structure.subject", _CREATURE_SUBJECT_FIELDS)
    for field in ("family_id", "species_id", "form_id"):
        _slug(subject[field], f"$.creature_structure.subject.{field}")

    landmarks_raw = root["landmarks"]
    if type(landmarks_raw) is not list:
        _fail("invalid_type", "$.creature_structure.landmarks", "must be a JSON array")
    landmarks = cast(list[object], landmarks_raw)
    if not 1 <= len(landmarks) <= MAX_PROFILE_LANDMARKS_V1:
        _fail("invalid_landmark_count", "$.creature_structure.landmarks", f"count must be in [1, {MAX_PROFILE_LANDMARKS_V1}]")

    landmark_ids: set[str] = set()
    landmark_records: dict[str, tuple[str | None, str | None, str]] = {}
    for index, raw in enumerate(landmarks):
        path = f"$.creature_structure.landmarks[{index}]"
        landmark = _object(raw, path, _LANDMARK_FIELDS)
        landmark_id = _slug(landmark["landmark_id"], f"{path}.landmark_id")
        if landmark_id in landmark_ids:
            _fail("duplicate_landmark", f"{path}.landmark_id", f"duplicate landmark id {landmark_id!r}")
        landmark_ids.add(landmark_id)
        _text(landmark["label"], f"{path}.label", maximum=128)
        parent = _nullable_slug(landmark["parent_landmark_id"], f"{path}.parent_landmark_id")
        mirror = _nullable_slug(landmark["mirror_landmark_id"], f"{path}.mirror_landmark_id")
        if parent == landmark_id:
            _fail("self_landmark_reference", f"{path}.parent_landmark_id", "landmark cannot parent itself")
        if mirror == landmark_id:
            _fail("self_landmark_reference", f"{path}.mirror_landmark_id", "landmark cannot mirror itself")
        landmark_records[landmark_id] = (parent, mirror, path)

    for landmark_id, (parent, mirror, path) in landmark_records.items():
        for field, ref in (("parent_landmark_id", parent), ("mirror_landmark_id", mirror)):
            if ref is not None and ref not in landmark_ids:
                _fail("unknown_landmark_reference", f"{path}.{field}", f"unknown landmark id {ref!r}")
        if mirror is not None:
            peer_mirror = landmark_records[mirror][1]
            if peer_mirror != landmark_id:
                _fail("nonreciprocal_mirror", f"{path}.mirror_landmark_id", f"mirror landmark {mirror!r} must point back to {landmark_id!r}")

    for landmark_id in landmark_ids:
        seen: set[str] = set()
        current: str | None = landmark_id
        while current is not None:
            if current in seen:
                _fail("landmark_parent_cycle", "$.creature_structure.landmarks", f"parent cycle includes {current!r}")
            seen.add(current)
            current = landmark_records[current][0]

    declarations_raw = root["category_declarations"]
    if type(declarations_raw) is not list:
        _fail("invalid_type", "$.creature_structure.category_declarations", "must be a JSON array")
    declarations = cast(list[object], declarations_raw)
    if len(declarations) != MAX_PROFILE_CATEGORY_DECLARATIONS_V1:
        _fail("invalid_category_count", "$.creature_structure.category_declarations", f"must contain exactly {MAX_PROFILE_CATEGORY_DECLARATIONS_V1} categories")

    statuses: dict[str, str] = {}
    for index, raw in enumerate(declarations):
        path = f"$.creature_structure.category_declarations[{index}]"
        declaration = _object(raw, path, _CATEGORY_DECLARATION_FIELDS)
        category = declaration["category"]
        if type(category) is not str or category not in _CREATURE_CATEGORY_SET:
            _fail("invalid_constraint_category", f"{path}.category", f"must be one of {list(_CREATURE_CATEGORIES)}")
        if category in statuses:
            _fail("duplicate_constraint_category", f"{path}.category", f"duplicate category {category!r}")
        status = declaration["status"]
        if type(status) is not str or status not in _CATEGORY_STATUS_VALUES:
            _fail("invalid_category_status", f"{path}.status", f"must be one of {sorted(_CATEGORY_STATUS_VALUES)}")
        _text(declaration["rationale"], f"{path}.rationale", maximum=512)
        unknown_id = declaration["unknown_id"]
        if status == "unknown":
            parsed_unknown = _slug(unknown_id, f"{path}.unknown_id")
            if parsed_unknown not in unknown_ids:
                _fail("unknown_unknown_reference", f"{path}.unknown_id", f"unknown profile unknown id {parsed_unknown!r}")
        elif unknown_id is not None:
            _fail("invalid_category_state", f"{path}.unknown_id", "must be null unless status is 'unknown'")
        if category in _ALWAYS_CONSTRAINED_CATEGORIES and status != "constrained":
            _fail("required_category_unconstrained", f"{path}.status", f"{category!r} must be constrained for a simple-creature profile")
        statuses[category] = status

    if frozenset(statuses) != _CREATURE_CATEGORY_SET:
        missing = sorted(_CREATURE_CATEGORY_SET - frozenset(statuses))
        _fail("missing_constraint_category", "$.creature_structure.category_declarations", f"missing categories {missing}")

    constraints_raw = root["constraints"]
    if type(constraints_raw) is not list:
        _fail("invalid_type", "$.creature_structure.constraints", "must be a JSON array")
    constraints = cast(list[object], constraints_raw)
    if not 1 <= len(constraints) <= MAX_PROFILE_STRUCTURAL_CONSTRAINTS_V1:
        _fail("invalid_structural_constraint_count", "$.creature_structure.constraints", f"count must be in [1, {MAX_PROFILE_STRUCTURAL_CONSTRAINTS_V1}]")

    constraint_ids: set[str] = set()
    category_counts = {category: 0 for category in _CREATURE_CATEGORIES}
    resolution_tolerance_count = 0
    for index, raw in enumerate(constraints):
        path = f"$.creature_structure.constraints[{index}]"
        constraint = _object(raw, path, _STRUCTURAL_CONSTRAINT_FIELDS)
        constraint_id = _slug(constraint["constraint_id"], f"{path}.constraint_id")
        if constraint_id in constraint_ids:
            _fail("duplicate_structural_constraint", f"{path}.constraint_id", f"duplicate structural constraint id {constraint_id!r}")
        constraint_ids.add(constraint_id)

        category = constraint["category"]
        if type(category) is not str or category not in _CREATURE_CATEGORY_SET:
            _fail("invalid_constraint_category", f"{path}.category", f"must be one of {list(_CREATURE_CATEGORIES)}")
        if statuses[category] != "constrained":
            _fail("constraint_for_unconstrained_category", f"{path}.category", f"category {category!r} is declared {statuses[category]!r}")
        category_counts[category] += 1

        mode = constraint["mode"]
        if type(mode) is not str or mode not in _CONSTRAINT_MODES:
            _fail("invalid_constraint_mode", f"{path}.mode", f"must be one of {sorted(_CONSTRAINT_MODES)}")
        landmark_refs = _string_ids(constraint["landmark_ids"], f"{path}.landmark_ids", maximum=MAX_PROFILE_LANDMARKS_V1)
        missing_landmarks = [ref for ref in landmark_refs if ref not in landmark_ids]
        if missing_landmarks:
            _fail("unknown_landmark_reference", f"{path}.landmark_ids", f"unknown landmark ids {missing_landmarks}")

        value_range = constraint["value_range"]
        if value_range is None:
            if mode != "hint":
                _fail("range_required", f"{path}.value_range", f"mode {mode!r} requires a finite value range")
            if category in ("relative-proportion", "articulation", "resolution-stylization"):
                _fail("range_required", f"{path}.value_range", f"category {category!r} requires a finite value range")
        else:
            bounds = _object(value_range, f"{path}.value_range", _VALUE_RANGE_FIELDS)
            minimum = _finite_number(bounds["minimum"], f"{path}.value_range.minimum")
            maximum = _finite_number(bounds["maximum"], f"{path}.value_range.maximum")
            if minimum > maximum:
                _fail("invalid_range", f"{path}.value_range", "minimum must be <= maximum")
            unit = bounds["unit"]
            if type(unit) is not str or unit not in _RANGE_UNITS:
                _fail("invalid_range_unit", f"{path}.value_range.unit", f"must be one of {sorted(_RANGE_UNITS)}")
            expected_unit = {
                "relative-proportion": "ratio",
                "articulation": "degrees",
                "resolution-stylization": "pixels",
            }.get(category)
            if expected_unit is not None and unit != expected_unit:
                _fail("invalid_range_unit", f"{path}.value_range.unit", f"{category!r} constraints require {expected_unit!r}")
            if unit == "ratio" and (minimum < 0 or maximum > 64):
                _fail("invalid_range", f"{path}.value_range", "ratio range must stay within [0, 64]")
            if unit == "degrees" and (minimum < -360 or maximum > 360):
                _fail("invalid_range", f"{path}.value_range", "degree range must stay within [-360, 360]")
            if unit == "pixels" and (minimum < 0 or maximum > 4096):
                _fail("invalid_range", f"{path}.value_range", "pixel range must stay within [0, 4096]")

        _text(constraint["text"], f"{path}.text", maximum=512)
        fact_refs = _string_ids(constraint["basis_fact_ids"], f"{path}.basis_fact_ids", maximum=MAX_PROFILE_FACTS_V1)
        missing_facts = [ref for ref in fact_refs if ref not in fact_ids]
        if missing_facts:
            _fail("unknown_fact_reference", f"{path}.basis_fact_ids", f"unknown fact ids {missing_facts}")
        confidence = constraint["confidence"]
        if type(confidence) is not str or confidence not in _CONFIDENCE_VALUES:
            _fail("invalid_confidence", f"{path}.confidence", f"must be one of {sorted(_CONFIDENCE_VALUES)}")

        if category == "resolution-stylization" and mode == "stylization-tolerance":
            resolution_tolerance_count += 1

    for category, status in statuses.items():
        count = category_counts[category]
        if status == "constrained" and count == 0:
            _fail("missing_category_constraint", "$.creature_structure.constraints", f"constrained category {category!r} has no constraint")
        if status != "constrained" and count != 0:
            _fail("constraint_for_unconstrained_category", "$.creature_structure.constraints", f"category {category!r} must not have constraints")

    if resolution_tolerance_count == 0:
        _fail("missing_stylization_tolerance", "$.creature_structure.constraints", "resolution-stylization requires at least one stylization-tolerance constraint")


def validate_morphology_profile(value: object) -> MorphologyProfileV1:
    root = _profile_object(value, "$")
    if root["schema"] != MORPHOLOGY_PROFILE_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {MORPHOLOGY_PROFILE_SCHEMA_V1!r}")
    _slug(root["profile_id"], "$.profile_id")
    _text(root["subject_label"], "$.subject_label", maximum=128)

    sources_raw = root["source_evidence"]
    if type(sources_raw) is not list:
        _fail("invalid_type", "$.source_evidence", "must be a JSON array")
    sources = cast(list[object], sources_raw)
    if not 1 <= len(sources) <= MAX_RESEARCH_SOURCES_V1:
        _fail("invalid_source_count", "$.source_evidence", f"count must be in [1, {MAX_RESEARCH_SOURCES_V1}]")
    source_ids: set[str] = set()
    for index, raw in enumerate(sources):
        path = f"$.source_evidence[{index}]"
        source = _object(raw, path, _SOURCE_FIELDS)
        source_id = _slug(source["source_id"], f"{path}.source_id")
        if source_id in source_ids:
            _fail("duplicate_source", f"{path}.source_id", f"duplicate source id {source_id!r}")
        source_ids.add(source_id)
        kind = source["kind"]
        if type(kind) is not str or kind not in _SOURCE_KINDS:
            _fail("invalid_source_kind", f"{path}.kind", f"must be one of {sorted(_SOURCE_KINDS)}")
        _text(source["locator"], f"{path}.locator", maximum=1024)
        _text(source["title"], f"{path}.title", maximum=256)
        retrieved = source["retrieved_at_utc"]
        if type(retrieved) is not str or _UTC.fullmatch(retrieved) is None:
            _fail("invalid_retrieved_at", f"{path}.retrieved_at_utc", "must be UTC YYYY-MM-DDTHH:MM:SSZ")

    facts_raw = root["observed_facts"]
    if type(facts_raw) is not list:
        _fail("invalid_type", "$.observed_facts", "must be a JSON array")
    facts = cast(list[object], facts_raw)
    if not 1 <= len(facts) <= MAX_PROFILE_FACTS_V1:
        _fail("invalid_fact_count", "$.observed_facts", f"count must be in [1, {MAX_PROFILE_FACTS_V1}]")
    fact_ids: set[str] = set()
    for index, raw in enumerate(facts):
        path = f"$.observed_facts[{index}]"
        fact = _object(raw, path, _FACT_FIELDS)
        fact_id = _slug(fact["fact_id"], f"{path}.fact_id")
        if fact_id in fact_ids:
            _fail("duplicate_fact", f"{path}.fact_id", f"duplicate fact id {fact_id!r}")
        fact_ids.add(fact_id)
        _text(fact["text"], f"{path}.text", maximum=512)
        refs = _string_ids(fact["source_ids"], f"{path}.source_ids", maximum=MAX_RESEARCH_SOURCES_V1)
        missing = [ref for ref in refs if ref not in source_ids]
        if missing:
            _fail("unknown_source_reference", f"{path}.source_ids", f"unknown source ids {missing}")

    constraints_raw = root["inferred_constraints"]
    if type(constraints_raw) is not list:
        _fail("invalid_type", "$.inferred_constraints", "must be a JSON array")
    constraints = cast(list[object], constraints_raw)
    if len(constraints) > MAX_PROFILE_CONSTRAINTS_V1:
        _fail("invalid_constraint_count", "$.inferred_constraints", f"at most {MAX_PROFILE_CONSTRAINTS_V1} constraints are allowed")
    constraint_ids: set[str] = set()
    for index, raw in enumerate(constraints):
        path = f"$.inferred_constraints[{index}]"
        constraint = _object(raw, path, _CONSTRAINT_FIELDS)
        constraint_id = _slug(constraint["constraint_id"], f"{path}.constraint_id")
        if constraint_id in constraint_ids:
            _fail("duplicate_constraint", f"{path}.constraint_id", f"duplicate constraint id {constraint_id!r}")
        constraint_ids.add(constraint_id)
        _text(constraint["text"], f"{path}.text", maximum=512)
        refs = _string_ids(constraint["basis_fact_ids"], f"{path}.basis_fact_ids", maximum=MAX_PROFILE_FACTS_V1)
        missing = [ref for ref in refs if ref not in fact_ids]
        if missing:
            _fail("unknown_fact_reference", f"{path}.basis_fact_ids", f"unknown fact ids {missing}")
        confidence = constraint["confidence"]
        if type(confidence) is not str or confidence not in _CONFIDENCE_VALUES:
            _fail("invalid_confidence", f"{path}.confidence", f"must be one of {sorted(_CONFIDENCE_VALUES)}")

    conventions_raw = root["artistic_conventions"]
    if type(conventions_raw) is not list:
        _fail("invalid_type", "$.artistic_conventions", "must be a JSON array")
    conventions = cast(list[object], conventions_raw)
    if len(conventions) > MAX_PROFILE_CONVENTIONS_V1:
        _fail("invalid_convention_count", "$.artistic_conventions", f"at most {MAX_PROFILE_CONVENTIONS_V1} conventions are allowed")
    convention_ids: set[str] = set()
    for index, raw in enumerate(conventions):
        path = f"$.artistic_conventions[{index}]"
        convention = _object(raw, path, _CONVENTION_FIELDS)
        convention_id = _slug(convention["convention_id"], f"{path}.convention_id")
        if convention_id in convention_ids:
            _fail("duplicate_convention", f"{path}.convention_id", f"duplicate convention id {convention_id!r}")
        convention_ids.add(convention_id)
        _text(convention["text"], f"{path}.text", maximum=512)

    unknowns_raw = root["unknowns"]
    if type(unknowns_raw) is not list:
        _fail("invalid_type", "$.unknowns", "must be a JSON array")
    unknowns = cast(list[object], unknowns_raw)
    if len(unknowns) > MAX_PROFILE_UNKNOWNS_V1:
        _fail("invalid_unknown_count", "$.unknowns", f"at most {MAX_PROFILE_UNKNOWNS_V1} unknowns are allowed")
    unknown_ids: set[str] = set()
    for index, raw in enumerate(unknowns):
        path = f"$.unknowns[{index}]"
        unknown = _object(raw, path, _UNKNOWN_FIELDS)
        unknown_id = _slug(unknown["unknown_id"], f"{path}.unknown_id")
        if unknown_id in unknown_ids:
            _fail("duplicate_unknown", f"{path}.unknown_id", f"duplicate unknown id {unknown_id!r}")
        unknown_ids.add(unknown_id)
        _text(unknown["text"], f"{path}.text", maximum=512)

    if "creature_structure" in root:
        _validate_creature_structure(root["creature_structure"], fact_ids=fact_ids, unknown_ids=unknown_ids)

    return cast(MorphologyProfileV1, value)


def validate_simple_creature_morphology_profile(value: object) -> MorphologyProfileV1:
    profile = validate_morphology_profile(value)
    if "creature_structure" not in profile:
        _fail("missing_creature_structure", "$.creature_structure", "simple-creature profiles require structured morphology constraints")
    return profile


def morphology_profile_canonical_bytes(profile: object) -> bytes:
    validated = validate_morphology_profile(profile)
    return json.dumps(validated, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def morphology_profile_sha256(profile: object) -> str:
    return sha256(morphology_profile_canonical_bytes(profile)).hexdigest()


def validate_morphology_profile_reference(ref: object, profile: object) -> MorphologyProfileRefV1:
    validated_ref = _profile_ref(ref, "$ref")
    validated_profile = validate_morphology_profile(profile)
    if validated_ref["profile_id"] != validated_profile["profile_id"]:
        _fail("profile_id_mismatch", "$ref.profile_id", "reference profile_id does not match profile")
    digest = morphology_profile_sha256(validated_profile)
    if validated_ref["sha256"] != digest:
        _fail("profile_digest_mismatch", "$ref.sha256", "reference digest does not match canonical profile bytes")
    return validated_ref
