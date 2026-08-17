from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re
from typing import cast

from .art_intent_validation import ArtIntentValidationError, validate_art_intent
from .asset_set import MAX_SHARED_PROFILES_V1, AssetSetV1
from .asset_set_validation import AssetSetValidationError, validate_asset_set
from .asset_set_schedule import (
    ASSET_REQUEST_SCHEMA_V1,
    ASSET_SET_REQUEST_SCHEMA_V1,
    ASSET_SET_SCHEDULE_SCHEMA_V1,
    MAX_ASSET_REQUEST_INSTRUCTION_CHARS_V1,
    AssetRequestV1,
    AssetSetRequestV1,
    AssetSetScheduleV1,
)

_ASSET_REQUEST_FIELDS = frozenset(("schema", "instruction", "art_intent", "profile_refs"))
_PROFILE_REF_FIELDS = frozenset(("kind", "profile_id", "profile_schema", "sha256"))
_SET_REQUEST_FIELDS = frozenset(("schema", "asset_set_id", "asset_set_sha256", "members"))
_SET_REQUEST_MEMBER_FIELDS = frozenset(("member_id", "request_ref", "request_sha256"))
_SCHEDULE_FIELDS = frozenset(
    (
        "schema",
        "asset_set_id",
        "asset_set_sha256",
        "request_sha256",
        "member_authority",
        "ordering",
        "dispatch_policy",
        "failure_policy",
        "max_concurrency",
        "aggregate_budget",
        "members",
    )
)
_SCHEDULE_MEMBER_FIELDS = frozenset(("ordinal", "member_id", "request_ref", "request_sha256"))
_BUDGET_FIELDS = frozenset(("max_provider_calls", "max_pixel_edits", "max_wall_time_ms"))
_PROFILE_KINDS = frozenset(("style", "palette", "morphology"))
_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = re.compile(r"^tracepixel\.[a-z0-9._-]+\.v[1-9][0-9]*$")


class AssetSetScheduleValidationError(ValueError):
    """Deterministic P8-B0 request/schedule rejection with stable code/path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise AssetSetScheduleValidationError(code, path, message)


def _object(value: object, path: str, fields: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    obj = cast(dict[object, object], value)
    if not all(type(key) is str for key in obj):
        _fail("invalid_fields", path, "object keys must be strings")
    typed = cast(dict[str, object], obj)
    actual = frozenset(typed)
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail("invalid_fields", path, "; ".join(parts))
    return typed


def _slug(value: object, path: str) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    if _SLUG.fullmatch(value) is None:
        _fail("invalid_id", path, "must be a lowercase ASCII slug of length 1..64")
    return value


def _text(value: object, path: str, *, maximum: int) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    if not 1 <= len(value) <= maximum:
        _fail("invalid_value", path, f"length must be in [1, {maximum}]")
    return value


def _digest(value: object, path: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail("invalid_digest", path, "must be 64 lowercase hexadecimal characters")
    return value


def _canonical_sha256(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail("invalid_json", "$", f"must be canonical-JSON serializable: {exc}")
    return sha256(payload).hexdigest()


def asset_set_sha256(asset_set: object) -> str:
    """Canonical digest of one already-valid AssetSet contract."""

    try:
        validate_asset_set(asset_set)
    except AssetSetValidationError as exc:
        _fail("invalid_asset_set", f"$asset_set{exc.path[1:]}", f"{exc.code}: {exc.message}")
    return _canonical_sha256(asset_set)


def _profile_refs(value: object, path: str) -> list[dict[str, object]]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    refs = cast(list[object], value)
    if len(refs) > MAX_SHARED_PROFILES_V1:
        _fail("too_many_profiles", path, f"at most {MAX_SHARED_PROFILES_V1} profile refs are allowed")
    result: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(refs):
        ref_path = f"{path}[{index}]"
        ref = _object(raw, ref_path, _PROFILE_REF_FIELDS)
        kind = ref["kind"]
        if type(kind) is not str or kind not in _PROFILE_KINDS:
            _fail("invalid_profile_kind", f"{ref_path}.kind", f"must be one of {sorted(_PROFILE_KINDS)}")
        profile_id = _slug(ref["profile_id"], f"{ref_path}.profile_id")
        schema = _text(ref["profile_schema"], f"{ref_path}.profile_schema", maximum=128)
        if _SCHEMA.fullmatch(schema) is None:
            _fail(
                "invalid_profile_schema",
                f"{ref_path}.profile_schema",
                "must be a versioned tracepixel.*.vN schema id",
            )
        _digest(ref["sha256"], f"{ref_path}.sha256")
        identity = (kind, profile_id)
        if identity in seen:
            _fail("duplicate_profile", ref_path, f"duplicate profile ref {identity!r}")
        seen.add(identity)
        result.append(ref)
    return result


def _profile_key(ref: Mapping[str, object]) -> tuple[object, object, object, object]:
    return (ref.get("kind"), ref.get("profile_id"), ref.get("profile_schema"), ref.get("sha256"))


def validate_asset_request(
    request: object,
    *,
    shared_profiles: object | None = None,
) -> AssetRequestV1:
    """Validate one immutable single-asset request without invoking provider or raster authority."""

    root = _object(request, "$", _ASSET_REQUEST_FIELDS)
    if root["schema"] != ASSET_REQUEST_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {ASSET_REQUEST_SCHEMA_V1!r}")

    instruction = _text(
        root["instruction"],
        "$.instruction",
        maximum=MAX_ASSET_REQUEST_INSTRUCTION_CHARS_V1,
    )
    if not instruction.strip():
        _fail("invalid_instruction", "$.instruction", "must contain non-whitespace text")

    try:
        validate_art_intent(root["art_intent"])
    except ArtIntentValidationError as exc:
        _fail("invalid_art_intent", f"$.art_intent{exc.path[1:]}", f"{exc.code}: {exc.message}")

    refs = _profile_refs(root["profile_refs"], "$.profile_refs")
    if shared_profiles is not None:
        if type(shared_profiles) is not list:
            _fail("invalid_type", "$context.shared_profiles", "must be a JSON array")
        allowed = {
            _profile_key(cast(dict[str, object], item))
            for item in cast(list[object], shared_profiles)
            if type(item) is dict
        }
        for index, ref in enumerate(refs):
            if _profile_key(ref) not in allowed:
                _fail(
                    "unshared_profile",
                    f"$.profile_refs[{index}]",
                    "member request may reference only exact digest-pinned AssetSet shared profiles",
                )

    return cast(AssetRequestV1, request)


def asset_request_sha256(request: object, *, shared_profiles: object | None = None) -> str:
    validate_asset_request(request, shared_profiles=shared_profiles)
    return _canonical_sha256(request)


def validate_asset_set_request(request_set: object, asset_set: object) -> AssetSetRequestV1:
    """Validate exact member identity/order/digest bindings against one AssetSet."""

    try:
        validated_set = validate_asset_set(asset_set)
    except AssetSetValidationError as exc:
        _fail("invalid_asset_set", f"$asset_set{exc.path[1:]}", f"{exc.code}: {exc.message}")
    root = _object(request_set, "$", _SET_REQUEST_FIELDS)
    if root["schema"] != ASSET_SET_REQUEST_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {ASSET_SET_REQUEST_SCHEMA_V1!r}")
    if root["asset_set_id"] != validated_set["asset_set_id"]:
        _fail("asset_set_id_mismatch", "$.asset_set_id", "must match the bound AssetSet id")
    expected_set_digest = asset_set_sha256(validated_set)
    actual_set_digest = _digest(root["asset_set_sha256"], "$.asset_set_sha256")
    if actual_set_digest != expected_set_digest:
        _fail("asset_set_digest_mismatch", "$.asset_set_sha256", "must match the canonical AssetSet digest")

    raw_members = root["members"]
    if type(raw_members) is not list:
        _fail("invalid_type", "$.members", "must be a JSON array")
    members = cast(list[object], raw_members)
    declared = cast(list[dict[str, object]], validated_set["members"])
    if len(members) != len(declared):
        _fail("member_count_mismatch", "$.members", "must bind every declared AssetSet member exactly once")

    seen: set[str] = set()
    for index, (raw, expected) in enumerate(zip(members, declared, strict=True)):
        path = f"$.members[{index}]"
        member = _object(raw, path, _SET_REQUEST_MEMBER_FIELDS)
        member_id = _slug(member["member_id"], f"{path}.member_id")
        if member_id in seen:
            _fail("duplicate_member", f"{path}.member_id", f"duplicate member id {member_id!r}")
        seen.add(member_id)
        if member_id != expected["member_id"]:
            _fail("member_order_mismatch", f"{path}.member_id", "must preserve declared AssetSet member order")
        request_ref = _text(member["request_ref"], f"{path}.request_ref", maximum=256)
        if request_ref != expected["request_ref"]:
            _fail("request_ref_mismatch", f"{path}.request_ref", "must exactly match the AssetSet member request_ref")
        _digest(member["request_sha256"], f"{path}.request_sha256")

    return cast(AssetSetRequestV1, request_set)


def validate_asset_set_request_payloads(
    request_set: object,
    asset_set: object,
    request_payloads: Mapping[str, object],
) -> AssetSetRequestV1:
    """Verify every referenced member request payload before it becomes schedulable."""

    validated_set_request = validate_asset_set_request(request_set, asset_set)
    validated_set = cast(AssetSetV1, asset_set)
    expected_refs = [member["request_ref"] for member in validated_set_request["members"]]
    if any(type(key) is not str for key in request_payloads):
        _fail("invalid_payload_map", "$context.request_payloads", "keys must be request_ref strings")
    if set(request_payloads) != set(expected_refs):
        _fail(
            "payload_set_mismatch",
            "$context.request_payloads",
            "must contain exactly one payload for every request_ref and no extras",
        )

    shared_profiles = validated_set["shared_profiles"]
    for index, member in enumerate(validated_set_request["members"]):
        ref = member["request_ref"]
        payload = request_payloads[ref]
        try:
            digest = asset_request_sha256(payload, shared_profiles=shared_profiles)
        except AssetSetScheduleValidationError as exc:
            _fail(
                "invalid_member_request",
                f"$context.request_payloads[{ref!r}]{exc.path[1:]}",
                f"{exc.code}: {exc.message}",
            )
        if digest != member["request_sha256"]:
            _fail(
                "request_digest_mismatch",
                f"$.members[{index}].request_sha256",
                "does not match the canonical referenced AssetRequest payload digest",
            )
    return validated_set_request


def asset_set_request_sha256(
    request_set: object,
    asset_set: object,
    request_payloads: Mapping[str, object],
) -> str:
    validate_asset_set_request_payloads(request_set, asset_set, request_payloads)
    return _canonical_sha256(request_set)


def build_asset_set_schedule(
    request_set: object,
    asset_set: object,
    request_payloads: Mapping[str, object],
) -> AssetSetScheduleV1:
    """Derive one immutable declared-order queue; no member is executed here."""

    validated_request = validate_asset_set_request_payloads(request_set, asset_set, request_payloads)
    validated_set = cast(AssetSetV1, asset_set)
    execution = validated_set["execution"]
    schedule: AssetSetScheduleV1 = {
        "schema": ASSET_SET_SCHEDULE_SCHEMA_V1,
        "asset_set_id": validated_set["asset_set_id"],
        "asset_set_sha256": asset_set_sha256(validated_set),
        "request_sha256": _canonical_sha256(validated_request),
        "member_authority": execution["member_authority"],
        "ordering": execution["ordering"],
        "dispatch_policy": "declared-order-bounded-concurrency",
        "failure_policy": execution["failure_policy"],
        "max_concurrency": execution["max_concurrency"],
        "aggregate_budget": {
            "max_provider_calls": execution["aggregate_budget"]["max_provider_calls"],
            "max_pixel_edits": execution["aggregate_budget"]["max_pixel_edits"],
            "max_wall_time_ms": execution["aggregate_budget"]["max_wall_time_ms"],
        },
        "members": [
            {
                "ordinal": index,
                "member_id": member["member_id"],
                "request_ref": member["request_ref"],
                "request_sha256": member["request_sha256"],
            }
            for index, member in enumerate(validated_request["members"])
        ],
    }
    return schedule


def validate_asset_set_schedule(
    schedule: object,
    request_set: object,
    asset_set: object,
    request_payloads: Mapping[str, object],
) -> AssetSetScheduleV1:
    """Validate a schedule as the exact deterministic projection of its frozen inputs."""

    expected = build_asset_set_schedule(request_set, asset_set, request_payloads)
    root = _object(schedule, "$", _SCHEDULE_FIELDS)
    if root["schema"] != ASSET_SET_SCHEDULE_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {ASSET_SET_SCHEDULE_SCHEMA_V1!r}")

    for field in (
        "asset_set_id",
        "asset_set_sha256",
        "request_sha256",
        "member_authority",
        "ordering",
        "dispatch_policy",
        "failure_policy",
    ):
        if root[field] != expected[field]:
            _fail("schedule_mismatch", f"$.{field}", "must equal the deterministic schedule projection")

    if type(root["max_concurrency"]) is not int:
        _fail("invalid_type", "$.max_concurrency", "must be an exact integer")
    if root["max_concurrency"] != expected["max_concurrency"]:
        _fail("schedule_mismatch", "$.max_concurrency", "must equal the deterministic schedule projection")

    budget = _object(root["aggregate_budget"], "$.aggregate_budget", _BUDGET_FIELDS)
    for field in _BUDGET_FIELDS:
        if type(budget[field]) is not int:
            _fail("invalid_type", f"$.aggregate_budget.{field}", "must be an exact integer")
    if budget != expected["aggregate_budget"]:
        _fail("schedule_mismatch", "$.aggregate_budget", "must exactly retain the AssetSet aggregate budget")

    raw_members = root["members"]
    if type(raw_members) is not list:
        _fail("invalid_type", "$.members", "must be a JSON array")
    members = cast(list[object], raw_members)
    if len(members) != len(expected["members"]):
        _fail("schedule_mismatch", "$.members", "must contain every request member exactly once")
    for index, (raw, expected_member) in enumerate(zip(members, expected["members"], strict=True)):
        path = f"$.members[{index}]"
        member = _object(raw, path, _SCHEDULE_MEMBER_FIELDS)
        if type(member["ordinal"]) is not int:
            _fail("invalid_type", f"{path}.ordinal", "must be an exact integer")
        if member != expected_member:
            _fail("schedule_mismatch", path, "must preserve exact declared-order member projection")

    return cast(AssetSetScheduleV1, schedule)
