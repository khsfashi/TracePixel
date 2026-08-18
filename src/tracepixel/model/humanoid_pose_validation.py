from __future__ import annotations

from hashlib import sha256
import json
import math
import re
from typing import cast

from .humanoid_pose import (
    HUMANOID_POSE_SCHEMA_V1,
    MAX_HUMANOID_EQUIPMENT_ATTACHMENTS_V1,
    MAX_HUMANOID_POSE_RELATIONS_V1,
    HumanoidPoseRefV1,
    HumanoidPoseV1,
)
from .humanoid_profile import MAX_HUMANOID_LANDMARKS_V1, HumanoidProfileV1
from .humanoid_profile_validation import (
    HumanoidProfileValidationError,
    validate_humanoid_profile,
    validate_humanoid_profile_reference,
)

_ROOT_FIELDS = frozenset(("schema", "pose_id", "pose_name", "profile_ref", "orientation_intent", "relations", "equipment_attachments"))
_ORIENTATION_FIELDS = frozenset(("facing", "description"))
_RELATION_FIELDS = frozenset(("relation_id", "kind", "mode", "landmark_ids", "value_range", "text"))
_RANGE_FIELDS = frozenset(("minimum", "maximum", "unit"))
_ATTACHMENT_FIELDS = frozenset(("attachment_id", "anchor_id", "equipment_id", "attachment_class", "side_intent", "occupancy_intent", "overlap_occlusion_intent", "text"))
_REF_FIELDS = frozenset(("pose_id", "pose_schema", "sha256"))
_FACINGS = frozenset(("left", "right", "front", "rear", "three-quarter-left", "three-quarter-right"))
_RELATION_KINDS = frozenset(("landmark-relation", "articulation", "support-contact", "balance-contact", "silhouette-facing"))
_REQUIRED_RELATION_KINDS = frozenset(("articulation", "support-contact", "balance-contact", "silhouette-facing"))
_MODES = frozenset(("required-range", "hint", "stylization-tolerance"))
_RANGE_UNITS = frozenset(("ratio", "degrees", "pixels"))
_SIDES = frozenset(("center", "left", "right"))
_OCCUPANCY = frozenset(("occupied", "clear"))
_OCCLUSION = frozenset(("in-front", "behind", "mixed", "none"))
_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class HumanoidPoseValidationError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise HumanoidPoseValidationError(code, path, message)


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


def _text(value: object, path: str, maximum: int) -> str:
    if type(value) is not str or not 1 <= len(value) <= maximum:
        _fail("invalid_text", path, f"must be a non-empty string of length <= {maximum}")
    return value


def _ids(value: object, path: str, maximum: int) -> list[str]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    raw = cast(list[object], value)
    if not 1 <= len(raw) <= maximum:
        _fail("invalid_count", path, f"count must be in [1, {maximum}]")
    parsed = [_slug(item, f"{path}[{index}]") for index, item in enumerate(raw)]
    if len(parsed) != len(set(parsed)):
        _fail("duplicate_reference", path, "references must be unique")
    return parsed


def _finite_range(value: object, path: str) -> tuple[float, float, str]:
    bounds = _object(value, path, _RANGE_FIELDS)
    numbers: list[float] = []
    for field in ("minimum", "maximum"):
        raw = bounds[field]
        if type(raw) not in (int, float):
            _fail("invalid_type", f"{path}.{field}", "must be a JSON number")
        number = float(raw)
        if not math.isfinite(number):
            _fail("invalid_range", f"{path}.{field}", "must be finite")
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
    return minimum, maximum, cast(str, unit)


def _profile_structure(profile: HumanoidProfileV1) -> tuple[set[str], set[str], dict[str, dict[str, object]]]:
    landmarks = cast(list[object], profile["landmarks"])
    landmark_ids = {
        cast(str, cast(dict[str, object], item)["landmark_id"])
        for item in landmarks
    }
    support_ids = {
        cast(str, item)
        for item in cast(list[object], profile["support_landmark_ids"])
    }
    anchors = cast(list[object], profile["equipment_anchors"])
    anchors_by_id = {
        cast(str, cast(dict[str, object], item)["anchor_id"]): cast(dict[str, object], item)
        for item in anchors
    }
    return landmark_ids, support_ids, anchors_by_id


def validate_humanoid_pose(value: object, humanoid_profile: object) -> HumanoidPoseV1:
    try:
        profile = validate_humanoid_profile(humanoid_profile)
    except HumanoidProfileValidationError as exc:
        _fail("invalid_humanoid_profile", "$profile", str(exc))

    root = _object(value, "$", _ROOT_FIELDS)
    if root["schema"] != HUMANOID_POSE_SCHEMA_V1:
        _fail("unsupported_schema", "$.schema", f"expected {HUMANOID_POSE_SCHEMA_V1!r}")
    _slug(root["pose_id"], "$.pose_id")
    _text(root["pose_name"], "$.pose_name", 128)

    try:
        validate_humanoid_profile_reference(root["profile_ref"], profile)
    except HumanoidProfileValidationError as exc:
        _fail("profile_binding_mismatch", "$.profile_ref", str(exc))

    orientation = _object(root["orientation_intent"], "$.orientation_intent", _ORIENTATION_FIELDS)
    facing = orientation["facing"]
    if type(facing) is not str or facing not in _FACINGS:
        _fail("invalid_facing", "$.orientation_intent.facing", f"must be one of {sorted(_FACINGS)}")
    _text(orientation["description"], "$.orientation_intent.description", 512)

    landmark_ids, support_ids, anchors_by_id = _profile_structure(profile)

    relations_raw = root["relations"]
    if type(relations_raw) is not list:
        _fail("invalid_type", "$.relations", "must be a JSON array")
    relations = cast(list[object], relations_raw)
    if not 1 <= len(relations) <= MAX_HUMANOID_POSE_RELATIONS_V1:
        _fail("invalid_relation_count", "$.relations", f"count must be in [1, {MAX_HUMANOID_POSE_RELATIONS_V1}]")

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
        kind_str = cast(str, kind)
        seen_kinds.add(kind_str)

        mode = relation["mode"]
        if type(mode) is not str or mode not in _MODES:
            _fail("invalid_constraint_mode", f"{path}.mode", f"must be one of {sorted(_MODES)}")
        mode_str = cast(str, mode)

        refs = _ids(relation["landmark_ids"], f"{path}.landmark_ids", MAX_HUMANOID_LANDMARKS_V1)
        missing = [item for item in refs if item not in landmark_ids]
        if missing:
            _fail("unknown_landmark_reference", f"{path}.landmark_ids", f"unknown landmark ids {missing}")

        value_range = relation["value_range"]
        parsed_range: tuple[float, float, str] | None = None
        if value_range is not None:
            parsed_range = _finite_range(value_range, f"{path}.value_range")
        if mode_str in ("required-range", "stylization-tolerance") and parsed_range is None:
            _fail("range_required", f"{path}.value_range", f"mode {mode_str!r} requires a finite value range")
        if mode_str == "hint" and parsed_range is not None:
            _fail("range_for_hint", f"{path}.value_range", "hint relations must not carry a numeric range")

        if kind_str == "articulation":
            if len(refs) < 2:
                _fail("articulation_landmarks_required", f"{path}.landmark_ids", "articulation requires at least two known landmarks")
            if mode_str != "required-range" or parsed_range is None:
                _fail("bounded_articulation_required", path, "articulation requires required-range mode with a finite degree range")
            if parsed_range[2] != "degrees":
                _fail("invalid_range_unit", f"{path}.value_range.unit", "articulation requires 'degrees'")
        elif kind_str == "landmark-relation":
            if mode_str == "stylization-tolerance" and parsed_range is not None and parsed_range[2] != "pixels":
                _fail("invalid_range_unit", f"{path}.value_range.unit", "stylization-tolerance landmark relations require 'pixels'")
        elif kind_str == "support-contact":
            if mode_str != "hint" or value_range is not None:
                _fail("invalid_relation_mode", path, "support-contact is declarative in v1 and must use hint mode")
            non_support = [item for item in refs if item not in support_ids]
            if non_support:
                _fail("non_support_contact", f"{path}.landmark_ids", f"support-contact landmarks must be declared profile supports: {non_support}")
        elif kind_str == "balance-contact":
            if mode_str != "hint" or value_range is not None:
                _fail("invalid_relation_mode", path, "balance-contact is declarative in v1 and must use hint mode")
            if not any(item in support_ids for item in refs):
                _fail("balance_without_support", f"{path}.landmark_ids", "balance-contact must include at least one declared support landmark")
        elif kind_str == "silhouette-facing":
            if mode_str != "hint" or value_range is not None:
                _fail("invalid_relation_mode", path, "silhouette-facing is declarative in v1 and must use hint mode")

        _text(relation["text"], f"{path}.text", 512)

    missing_kinds = sorted(_REQUIRED_RELATION_KINDS - seen_kinds)
    if missing_kinds:
        _fail("missing_required_relation", "$.relations", f"missing required relation kinds {missing_kinds}")

    attachments_raw = root["equipment_attachments"]
    if type(attachments_raw) is not list:
        _fail("invalid_type", "$.equipment_attachments", "must be a JSON array")
    attachments = cast(list[object], attachments_raw)
    if not 1 <= len(attachments) <= MAX_HUMANOID_EQUIPMENT_ATTACHMENTS_V1:
        _fail("invalid_attachment_count", "$.equipment_attachments", f"count must be in [1, {MAX_HUMANOID_EQUIPMENT_ATTACHMENTS_V1}]")

    attachment_ids: set[str] = set()
    declared_anchor_ids: set[str] = set()
    for index, raw in enumerate(attachments):
        path = f"$.equipment_attachments[{index}]"
        attachment = _object(raw, path, _ATTACHMENT_FIELDS)
        attachment_id = _slug(attachment["attachment_id"], f"{path}.attachment_id")
        if attachment_id in attachment_ids:
            _fail("duplicate_attachment", f"{path}.attachment_id", f"duplicate attachment id {attachment_id!r}")
        attachment_ids.add(attachment_id)

        anchor_id = _slug(attachment["anchor_id"], f"{path}.anchor_id")
        if anchor_id not in anchors_by_id:
            _fail("unknown_equipment_anchor", f"{path}.anchor_id", f"unknown equipment anchor {anchor_id!r}")
        if anchor_id in declared_anchor_ids:
            _fail("duplicate_anchor_occupancy", f"{path}.anchor_id", "each anchor may have only one occupancy declaration")
        declared_anchor_ids.add(anchor_id)
        anchor = anchors_by_id[anchor_id]

        attachment_class = _slug(attachment["attachment_class"], f"{path}.attachment_class")
        if attachment_class != anchor["attachment_class"]:
            _fail("attachment_class_mismatch", f"{path}.attachment_class", "must match the retained profile anchor attachment class")

        side = attachment["side_intent"]
        if type(side) is not str or side not in _SIDES:
            _fail("invalid_side_intent", f"{path}.side_intent", f"must be one of {sorted(_SIDES)}")
        if side != anchor["side"]:
            _fail("anchor_side_mismatch", f"{path}.side_intent", "side intent must match the retained profile anchor side")

        occupancy = attachment["occupancy_intent"]
        if type(occupancy) is not str or occupancy not in _OCCUPANCY:
            _fail("invalid_occupancy_intent", f"{path}.occupancy_intent", f"must be one of {sorted(_OCCUPANCY)}")

        occlusion = attachment["overlap_occlusion_intent"]
        if type(occlusion) is not str or occlusion not in _OCCLUSION:
            _fail("invalid_occlusion_intent", f"{path}.overlap_occlusion_intent", f"must be one of {sorted(_OCCLUSION)}")

        equipment_id = attachment["equipment_id"]
        if occupancy == "occupied":
            _slug(equipment_id, f"{path}.equipment_id")
        else:
            if equipment_id is not None:
                _fail("clear_anchor_has_equipment", f"{path}.equipment_id", "clear occupancy requires equipment_id = null")
            if occlusion != "none":
                _fail("clear_anchor_has_occlusion", f"{path}.overlap_occlusion_intent", "clear occupancy requires overlap/occlusion intent 'none'")

        _text(attachment["text"], f"{path}.text", 512)

    return cast(HumanoidPoseV1, value)


def humanoid_pose_canonical_bytes(pose: object, humanoid_profile: object) -> bytes:
    validated = validate_humanoid_pose(pose, humanoid_profile)
    return json.dumps(validated, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def humanoid_pose_sha256(pose: object, humanoid_profile: object) -> str:
    return sha256(humanoid_pose_canonical_bytes(pose, humanoid_profile)).hexdigest()


def validate_humanoid_pose_reference(ref: object, pose: object, humanoid_profile: object) -> HumanoidPoseRefV1:
    validated_ref = _object(ref, "$ref", _REF_FIELDS)
    pose_id = _slug(validated_ref["pose_id"], "$ref.pose_id")
    if validated_ref["pose_schema"] != HUMANOID_POSE_SCHEMA_V1:
        _fail("invalid_pose_schema", "$ref.pose_schema", f"must equal {HUMANOID_POSE_SCHEMA_V1!r}")
    digest = validated_ref["sha256"]
    if type(digest) is not str or _SHA256.fullmatch(digest) is None:
        _fail("invalid_digest", "$ref.sha256", "must be 64 lowercase hexadecimal characters")
    validated_pose = validate_humanoid_pose(pose, humanoid_profile)
    if pose_id != validated_pose["pose_id"]:
        _fail("pose_id_mismatch", "$ref.pose_id", "must match the retained pose id")
    expected = humanoid_pose_sha256(validated_pose, humanoid_profile)
    if digest != expected:
        _fail("pose_digest_mismatch", "$ref.sha256", f"expected {expected}")
    return cast(HumanoidPoseRefV1, ref)
