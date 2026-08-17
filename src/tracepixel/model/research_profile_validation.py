from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import cast

from .research_profile import (
    FORM_RESOLUTION_SCHEMA_V1,
    MAX_PROFILE_CONSTRAINTS_V1,
    MAX_PROFILE_CONVENTIONS_V1,
    MAX_PROFILE_FACTS_V1,
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
_PROFILE_FIELDS = frozenset(("schema", "profile_id", "subject_label", "source_evidence", "observed_facts", "inferred_constraints", "artistic_conventions", "unknowns"))
_SOURCE_FIELDS = frozenset(("source_id", "kind", "locator", "title", "retrieved_at_utc"))
_FACT_FIELDS = frozenset(("fact_id", "text", "source_ids"))
_CONSTRAINT_FIELDS = frozenset(("constraint_id", "text", "basis_fact_ids", "confidence"))
_CONVENTION_FIELDS = frozenset(("convention_id", "text"))
_UNKNOWN_FIELDS = frozenset(("unknown_id", "text"))
_SOURCE_KINDS = frozenset(("official", "academic", "museum", "encyclopedic", "manufacturer", "general_web"))
_CONFIDENCE_VALUES = frozenset(("low", "medium", "high"))
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


def _bounded_int(value: object, path: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        _fail("invalid_type", path, "must be an exact integer")
    if not minimum <= value <= maximum:
        _fail("invalid_value", path, f"must be in [{minimum}, {maximum}]")
    return value


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


def validate_morphology_profile(value: object) -> MorphologyProfileV1:
    root = _object(value, "$", _PROFILE_FIELDS)
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

    return cast(MorphologyProfileV1, value)


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
