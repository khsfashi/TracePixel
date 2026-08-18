from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import cast

from .asset_set_schedule import ASSET_REQUEST_SCHEMA_V1, AssetRequestV1
from .asset_set_schedule_validation import (
    AssetSetScheduleValidationError,
    asset_request_sha256,
    validate_asset_request,
)
from .creature_pose import CreaturePoseV1
from .creature_pose_validation import (
    CreaturePoseValidationError,
    validate_creature_pose,
    validate_creature_pose_reference,
)
from .research_profile_validation import (
    ResearchProfileValidationError,
    validate_morphology_profile_reference,
    validate_simple_creature_morphology_profile,
)
from .simple_creature_request import (
    DETERMINISTIC_EVIDENCE_FACTS_V1,
    PERCEPTUAL_EVIDENCE_FACTS_V1,
    SIMPLE_CREATURE_EVIDENCE_POLICY_SCHEMA_V1,
    SIMPLE_CREATURE_REQUEST_SCHEMA_V1,
    SimpleCreatureEvidencePolicyRefV1,
    SimpleCreatureEvidencePolicyV1,
    SimpleCreatureRequestV1,
)

_REQUEST_FIELDS = frozenset(
    (
        "schema",
        "request_ref",
        "request_schema",
        "request_sha256",
        "morphology_ref",
        "pose_ref",
        "evidence_policy_ref",
    )
)
_POLICY_FIELDS = frozenset(
    (
        "schema",
        "deterministic_facts",
        "perceptual_facts",
        "vlm_is_deterministic_correctness",
        "final_aesthetic_acceptance",
    )
)
_POLICY_REF_FIELDS = frozenset(("policy_schema", "sha256"))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SimpleCreatureRequestValidationError(ValueError):
    """Deterministic C3 binding rejection with stable code/path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise SimpleCreatureRequestValidationError(code, path, message)


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


def _text(value: object, path: str, *, maximum: int) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    if not 1 <= len(value) <= maximum or not value.strip():
        _fail("invalid_value", path, f"must contain non-whitespace text of length 1..{maximum}")
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


def validate_simple_creature_evidence_policy(value: object) -> SimpleCreatureEvidencePolicyV1:
    root = _object(value, "$policy", _POLICY_FIELDS)
    if root["schema"] != SIMPLE_CREATURE_EVIDENCE_POLICY_SCHEMA_V1:
        _fail(
            "unsupported_policy_schema",
            "$policy.schema",
            f"expected {SIMPLE_CREATURE_EVIDENCE_POLICY_SCHEMA_V1!r}",
        )

    deterministic = root["deterministic_facts"]
    if type(deterministic) is not list or tuple(deterministic) != DETERMINISTIC_EVIDENCE_FACTS_V1:
        _fail(
            "deterministic_evidence_drift",
            "$policy.deterministic_facts",
            "must exactly match the frozen C0 deterministic evidence authority",
        )

    perceptual = root["perceptual_facts"]
    if type(perceptual) is not list or tuple(perceptual) != PERCEPTUAL_EVIDENCE_FACTS_V1:
        _fail(
            "perceptual_evidence_drift",
            "$policy.perceptual_facts",
            "must exactly match the frozen C0 perceptual evidence authority",
        )

    if root["vlm_is_deterministic_correctness"] is not False:
        _fail(
            "vlm_authority_drift",
            "$policy.vlm_is_deterministic_correctness",
            "VLM output may not become deterministic correctness",
        )
    if root["final_aesthetic_acceptance"] != "human":
        _fail(
            "aesthetic_authority_drift",
            "$policy.final_aesthetic_acceptance",
            "final aesthetic acceptance must remain human",
        )
    return cast(SimpleCreatureEvidencePolicyV1, value)


def simple_creature_evidence_policy_sha256(value: object) -> str:
    validate_simple_creature_evidence_policy(value)
    return _canonical_sha256(value)


def validate_simple_creature_evidence_policy_reference(
    ref: object,
    policy: object,
) -> SimpleCreatureEvidencePolicyRefV1:
    root = _object(ref, "$policy_ref", _POLICY_REF_FIELDS)
    if root["policy_schema"] != SIMPLE_CREATURE_EVIDENCE_POLICY_SCHEMA_V1:
        _fail(
            "invalid_policy_schema",
            "$policy_ref.policy_schema",
            f"must equal {SIMPLE_CREATURE_EVIDENCE_POLICY_SCHEMA_V1!r}",
        )
    digest = _digest(root["sha256"], "$policy_ref.sha256")
    expected = simple_creature_evidence_policy_sha256(policy)
    if digest != expected:
        _fail(
            "evidence_policy_digest_mismatch",
            "$policy_ref.sha256",
            "must match the canonical frozen evidence policy digest",
        )
    return cast(SimpleCreatureEvidencePolicyRefV1, ref)


def _validate_asset_request_context(asset_request: object) -> AssetRequestV1:
    try:
        request = validate_asset_request(asset_request)
    except AssetSetScheduleValidationError as exc:
        _fail("invalid_asset_request", f"$asset_request{exc.path[1:]}", f"{exc.code}: {exc.message}")

    art_intent = cast(dict[str, object], request["art_intent"])
    if art_intent.get("asset_class") != "simple-creature":
        _fail(
            "invalid_asset_class",
            "$asset_request.art_intent.asset_class",
            "simple-creature binding requires asset_class 'simple-creature'",
        )
    return request


def validate_simple_creature_request(
    value: object,
    *,
    asset_request: object,
    morphology_profile: object,
    creature_pose: object,
    evidence_policy: object,
) -> SimpleCreatureRequestV1:
    """Validate C3 bindings without provider calls, raster generation, physics, or perceptual scoring."""

    root = _object(value, "$", _REQUEST_FIELDS)
    if root["schema"] != SIMPLE_CREATURE_REQUEST_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {SIMPLE_CREATURE_REQUEST_SCHEMA_V1!r}")

    _text(root["request_ref"], "$.request_ref", maximum=256)
    if root["request_schema"] != ASSET_REQUEST_SCHEMA_V1:
        _fail(
            "asset_request_schema_mismatch",
            "$.request_schema",
            f"must equal {ASSET_REQUEST_SCHEMA_V1!r}",
        )

    request = _validate_asset_request_context(asset_request)
    actual_request_digest = asset_request_sha256(request)
    if _digest(root["request_sha256"], "$.request_sha256") != actual_request_digest:
        _fail(
            "asset_request_digest_mismatch",
            "$.request_sha256",
            "must bind the exact validated single-asset request payload",
        )

    try:
        profile = validate_simple_creature_morphology_profile(morphology_profile)
        validate_morphology_profile_reference(root["morphology_ref"], profile)
    except ResearchProfileValidationError as exc:
        _fail("morphology_binding_mismatch", "$.morphology_ref", str(exc))

    morphology_ref = cast(dict[str, object], root["morphology_ref"])
    expected_profile_ref = {
        "kind": "morphology",
        "profile_id": morphology_ref["profile_id"],
        "profile_schema": morphology_ref["profile_schema"],
        "sha256": morphology_ref["sha256"],
    }
    profile_refs = cast(list[object], request["profile_refs"])
    if expected_profile_ref not in profile_refs:
        _fail(
            "missing_bound_morphology_profile",
            "$asset_request.profile_refs",
            "single-asset request must contain the exact digest-pinned morphology profile ref",
        )

    try:
        pose = validate_creature_pose(creature_pose, profile)
        validate_creature_pose_reference(root["pose_ref"], pose, profile)
    except CreaturePoseValidationError as exc:
        _fail("pose_binding_mismatch", "$.pose_ref", str(exc))

    pose_morphology_ref = cast(dict[str, object], cast(CreaturePoseV1, pose)["morphology_ref"])
    if pose_morphology_ref != root["morphology_ref"]:
        _fail(
            "pose_morphology_binding_mismatch",
            "$.pose_ref",
            "pose and request must bind the same exact morphology reference",
        )

    validate_simple_creature_evidence_policy_reference(root["evidence_policy_ref"], evidence_policy)
    return cast(SimpleCreatureRequestV1, value)
