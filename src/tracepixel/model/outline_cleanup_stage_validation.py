from __future__ import annotations

from typing import cast

from .outline_cleanup_stage import (
    MAX_OUTLINE_CLEANUP_ACTIONS_V1,
    MAX_PIXELS_PER_OUTLINE_CLEANUP_ACTION_V1,
    OUTLINE_CLEANUP_STAGE_ID_V1,
    OUTLINE_CLEANUP_STAGE_SCHEMA_V1,
    OutlineCleanupStageV1,
)
from .palette_light_stage import PaletteLightStageV1
from .palette_light_stage_validation import (
    PaletteLightStageValidationError,
    validate_palette_light_stage,
)
from .validation import PixelProgramValidationError, validate_pixel_program

_OUTLINE_CLEANUP_STAGE_FIELDS = frozenset(("schema", "stage", "actions", "program"))
_OUTLINE_CLEANUP_ACTION_FIELDS = frozenset(("id", "kind"))
_OUTLINE_CLEANUP_ACTION_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")
_OUTLINE_CLEANUP_KINDS = frozenset(("outline", "cleanup"))


class OutlineCleanupStageValidationError(ValueError):
    """Deterministic P3-S6 rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise OutlineCleanupStageValidationError(code, path, message)


def _require_exact_object(
    value: object,
    path: str,
    fields: frozenset[str],
) -> dict[str, object]:
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


def _require_exact_array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def _validate_action_id(value: object, path: str) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    action_id = cast(str, value)
    if not 1 <= len(action_id) <= 32:
        _fail("invalid_outline_cleanup_action_id", path, "must contain 1..32 characters")
    if not "a" <= action_id[0] <= "z":
        _fail(
            "invalid_outline_cleanup_action_id",
            path,
            "must start with lowercase ASCII a-z",
        )
    if any(character not in _OUTLINE_CLEANUP_ACTION_ID_CHARS for character in action_id):
        _fail(
            "invalid_outline_cleanup_action_id",
            path,
            "must contain only lowercase ASCII a-z, digits, '_' or '-'",
        )
    return action_id


def _validate_action_kind(value: object, path: str) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    kind = cast(str, value)
    if kind not in _OUTLINE_CLEANUP_KINDS:
        _fail(
            "invalid_outline_cleanup_kind",
            path,
            "must be exactly 'outline' or 'cleanup'",
        )
    return kind


def _rebase_context(path: str) -> str:
    prefix = "$context.palette_light_stage"
    if path == "$":
        return prefix
    if path.startswith("$"):
        return f"{prefix}{path[1:]}"
    return prefix


def _program_path(path: str) -> str:
    if path == "$":
        return "$.program"
    if path.startswith("$"):
        return f"$.program{path[1:]}"
    return "$.program"


def validate_outline_cleanup_stage(
    stage: object,
    *,
    palette_light_stage: object,
) -> OutlineCleanupStageV1:
    """Validate bounded outline/cleanup patches against the authored S3 palette."""

    root = _require_exact_object(stage, "$", _OUTLINE_CLEANUP_STAGE_FIELDS)

    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != OUTLINE_CLEANUP_STAGE_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {OUTLINE_CLEANUP_STAGE_SCHEMA_V1!r}",
        )

    stage_id = root["stage"]
    if type(stage_id) is not str:
        _fail("invalid_type", "$.stage", "must be a string")
    if stage_id != OUTLINE_CLEANUP_STAGE_ID_V1:
        _fail(
            "invalid_stage",
            "$.stage",
            f"expected stage {OUTLINE_CLEANUP_STAGE_ID_V1!r}",
        )

    actions = _require_exact_array(root["actions"], "$.actions")
    if len(actions) > MAX_OUTLINE_CLEANUP_ACTIONS_V1:
        _fail(
            "too_many_outline_cleanup_actions",
            "$.actions",
            f"outline/cleanup stage supports at most {MAX_OUTLINE_CLEANUP_ACTIONS_V1} actions",
        )

    seen_ids: set[str] = set()
    for action_index, action_value in enumerate(actions):
        action_path = f"$.actions[{action_index}]"
        action = _require_exact_object(
            action_value,
            action_path,
            _OUTLINE_CLEANUP_ACTION_FIELDS,
        )
        action_id = _validate_action_id(action["id"], f"{action_path}.id")
        if action_id in seen_ids:
            _fail(
                "duplicate_outline_cleanup_action_id",
                f"{action_path}.id",
                f"duplicate outline/cleanup action id {action_id!r}",
            )
        seen_ids.add(action_id)
        _validate_action_kind(action["kind"], f"{action_path}.kind")

    try:
        palette_stage = validate_palette_light_stage(palette_light_stage)
    except PaletteLightStageValidationError as exc:
        _fail(
            "invalid_palette_light_stage",
            _rebase_context(exc.path),
            f"palette/light stage validation failed with {exc.code}: {exc.message}",
        )

    try:
        program = validate_pixel_program(root["program"])
    except PixelProgramValidationError as exc:
        _fail(
            "invalid_program",
            _program_path(exc.path),
            f"PixelProgram validation failed with {exc.code}: {exc.message}",
        )

    palette_stage = cast(PaletteLightStageV1, palette_stage)
    if program["canvas"] != palette_stage["program"]["canvas"]:
        _fail(
            "canvas_mismatch",
            "$.program.canvas",
            "outline/cleanup PixelProgram canvas must equal the S3 palette/light stage canvas",
        )

    operations = program["operations"]
    if len(actions) != len(operations):
        _fail(
            "action_operation_mismatch",
            "$.actions",
            "actions must map positionally one-to-one to PixelProgram operations",
        )

    palette_colors = {tuple(color["rgba"]) for color in palette_stage["palette"]}

    for action_index, operation in enumerate(operations):
        pixels = operation["pixels"]
        pixels_path = f"$.program.operations[{action_index}].pixels"
        if not pixels:
            _fail(
                "empty_outline_cleanup_action",
                pixels_path,
                f"outline/cleanup action at index {action_index} must contain at least one pixel edit",
            )
        if len(pixels) > MAX_PIXELS_PER_OUTLINE_CLEANUP_ACTION_V1:
            _fail(
                "too_many_outline_cleanup_pixels",
                pixels_path,
                "outline/cleanup action exceeds the bounded raw-patch edit budget of "
                f"{MAX_PIXELS_PER_OUTLINE_CLEANUP_ACTION_V1} pixels",
            )

        for pixel_index, pixel in enumerate(pixels):
            color = tuple(pixel[2:6])
            if color not in palette_colors:
                _fail(
                    "undeclared_palette_color",
                    f"{pixels_path}[{pixel_index}]",
                    "outline/cleanup pixel color must exactly match a color declared by the S3 palette",
                )

    return cast(OutlineCleanupStageV1, stage)
