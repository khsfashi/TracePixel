from __future__ import annotations

import re
from typing import cast

from .asset_set import (
    ASSET_SET_SCHEMA_V1,
    MAX_AGGREGATE_PIXEL_EDITS_V1,
    MAX_AGGREGATE_PROVIDER_CALLS_V1,
    MAX_AGGREGATE_WALL_TIME_MS_V1,
    MAX_ASSET_SET_MEMBERS_V1,
    MAX_BATCH_CONCURRENCY_V1,
    MAX_SHARED_PROFILES_V1,
    AssetSetV1,
)

_ASSET_SET_FIELDS = frozenset(("schema", "asset_set_id", "shared_profiles", "members", "execution"))
_PROFILE_FIELDS = frozenset(("kind", "profile_id", "profile_schema", "sha256"))
_MEMBER_FIELDS = frozenset(("member_id", "request_ref"))
_EXECUTION_FIELDS = frozenset(("member_authority", "ordering", "failure_policy", "max_concurrency", "aggregate_budget"))
_BUDGET_FIELDS = frozenset(("max_provider_calls", "max_pixel_edits", "max_wall_time_ms"))
_PROFILE_KINDS = frozenset(("style", "palette", "morphology"))
_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = re.compile(r"^tracepixel\.[a-z0-9._-]+\.v[1-9][0-9]*$")


class AssetSetValidationError(ValueError):
    """Deterministic AssetSet rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise AssetSetValidationError(code, path, message)


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
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    if _SLUG.fullmatch(value) is None:
        _fail("invalid_id", path, "must be a lowercase ASCII slug of length 1..64")
    return value


def _text(value: object, path: str, *, maximum: int = 256) -> str:
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


def _profiles(value: object) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", "$.shared_profiles", "must be a JSON array")
    profiles = cast(list[object], value)
    if len(profiles) > MAX_SHARED_PROFILES_V1:
        _fail("too_many_profiles", "$.shared_profiles", f"at most {MAX_SHARED_PROFILES_V1} profiles are allowed")
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(profiles):
        path = f"$.shared_profiles[{index}]"
        profile = _object(raw, path, _PROFILE_FIELDS)
        kind = profile["kind"]
        if type(kind) is not str or kind not in _PROFILE_KINDS:
            _fail("invalid_profile_kind", f"{path}.kind", f"must be one of {sorted(_PROFILE_KINDS)}")
        profile_id = _slug(profile["profile_id"], f"{path}.profile_id")
        profile_schema = _text(profile["profile_schema"], f"{path}.profile_schema", maximum=128)
        if _SCHEMA.fullmatch(profile_schema) is None:
            _fail("invalid_profile_schema", f"{path}.profile_schema", "must be a versioned tracepixel.*.vN schema id")
        digest = profile["sha256"]
        if type(digest) is not str or _SHA256.fullmatch(digest) is None:
            _fail("invalid_digest", f"{path}.sha256", "must be 64 lowercase hexadecimal characters")
        key = (kind, profile_id)
        if key in seen:
            _fail("duplicate_profile", path, f"duplicate shared profile {key!r}")
        seen.add(key)
    return profiles


def _members(value: object) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", "$.members", "must be a JSON array")
    members = cast(list[object], value)
    if not 1 <= len(members) <= MAX_ASSET_SET_MEMBERS_V1:
        _fail("invalid_member_count", "$.members", f"member count must be in [1, {MAX_ASSET_SET_MEMBERS_V1}]")
    seen: set[str] = set()
    for index, raw in enumerate(members):
        path = f"$.members[{index}]"
        member = _object(raw, path, _MEMBER_FIELDS)
        member_id = _slug(member["member_id"], f"{path}.member_id")
        _text(member["request_ref"], f"{path}.request_ref")
        if member_id in seen:
            _fail("duplicate_member", f"{path}.member_id", f"duplicate member id {member_id!r}")
        seen.add(member_id)
    return members


def validate_asset_set(asset_set: object) -> AssetSetV1:
    """Validate the P8-X0 batch envelope without executing or creating raster authority."""

    root = _object(asset_set, "$", _ASSET_SET_FIELDS)
    if root["schema"] != ASSET_SET_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {ASSET_SET_SCHEMA_V1!r}")
    _slug(root["asset_set_id"], "$.asset_set_id")
    _profiles(root["shared_profiles"])
    members = _members(root["members"])

    execution = _object(root["execution"], "$.execution", _EXECUTION_FIELDS)
    if execution["member_authority"] != "single-asset-pipeline":
        _fail("invalid_member_authority", "$.execution.member_authority", "must reuse the existing single-asset pipeline")
    if execution["ordering"] != "declared-member-order":
        _fail("invalid_ordering", "$.execution.ordering", "member list order must remain authoritative")
    if execution["failure_policy"] != "isolate-member":
        _fail("invalid_failure_policy", "$.execution.failure_policy", "member failures must be isolated")
    max_concurrency = _bounded_int(
        execution["max_concurrency"],
        "$.execution.max_concurrency",
        minimum=1,
        maximum=MAX_BATCH_CONCURRENCY_V1,
    )
    if max_concurrency > len(members):
        _fail("invalid_concurrency", "$.execution.max_concurrency", "cannot exceed declared member count")

    budget = _object(execution["aggregate_budget"], "$.execution.aggregate_budget", _BUDGET_FIELDS)
    _bounded_int(
        budget["max_provider_calls"],
        "$.execution.aggregate_budget.max_provider_calls",
        minimum=1,
        maximum=MAX_AGGREGATE_PROVIDER_CALLS_V1,
    )
    _bounded_int(
        budget["max_pixel_edits"],
        "$.execution.aggregate_budget.max_pixel_edits",
        minimum=1,
        maximum=MAX_AGGREGATE_PIXEL_EDITS_V1,
    )
    _bounded_int(
        budget["max_wall_time_ms"],
        "$.execution.aggregate_budget.max_wall_time_ms",
        minimum=1,
        maximum=MAX_AGGREGATE_WALL_TIME_MS_V1,
    )

    return cast(AssetSetV1, asset_set)
