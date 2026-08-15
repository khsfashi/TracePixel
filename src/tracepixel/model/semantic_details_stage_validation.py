from __future__ import annotations

from typing import cast

from .palette_light_stage import PaletteLightStageV1
from .palette_light_stage_validation import (
    PaletteLightStageValidationError,
    validate_palette_light_stage,
)
from .semantic_details_stage import (
    MAX_PIXELS_PER_SEMANTIC_DETAIL_V1,
    MAX_SEMANTIC_DETAILS_V1,
    SEMANTIC_DETAILS_STAGE_ID_V1,
    SEMANTIC_DETAILS_STAGE_SCHEMA_V1,
    SemanticDetailsStageV1,
)
from .validation import PixelProgramValidationError, validate_pixel_program

_SEMANTIC_DETAILS_STAGE_FIELDS = frozenset(("schema", "stage", "details", "program"))
_SEMANTIC_DETAIL_FIELDS = frozenset(("id",))
_SEMANTIC_DETAIL_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")


class SemanticDetailsStageValidationError(ValueError):
    """Deterministic P3-S5 rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise SemanticDetailsStageValidationError(code, path, message)


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


def _validate_detail_id(value: object, path: str) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    detail_id = cast(str, value)
    if not 1 <= len(detail_id) <= 32:
        _fail("invalid_semantic_detail_id", path, "must contain 1..32 characters")
    if not "a" <= detail_id[0] <= "z":
        _fail(
            "invalid_semantic_detail_id",
            path,
            "must start with lowercase ASCII a-z",
        )
    if any(character not in _SEMANTIC_DETAIL_ID_CHARS for character in detail_id):
        _fail(
            "invalid_semantic_detail_id",
            path,
            "must contain only lowercase ASCII a-z, digits, '_' or '-'",
        )
    return detail_id


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


def validate_semantic_details_stage(
    stage: object,
    *,
    palette_light_stage: object,
) -> SemanticDetailsStageV1:
    """Validate bounded semantic raw-pixel patches against the authored S3 palette."""

    root = _require_exact_object(stage, "$", _SEMANTIC_DETAILS_STAGE_FIELDS)

    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != SEMANTIC_DETAILS_STAGE_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {SEMANTIC_DETAILS_STAGE_SCHEMA_V1!r}",
        )

    stage_id = root["stage"]
    if type(stage_id) is not str:
        _fail("invalid_type", "$.stage", "must be a string")
    if stage_id != SEMANTIC_DETAILS_STAGE_ID_V1:
        _fail(
            "invalid_stage",
            "$.stage",
            f"expected stage {SEMANTIC_DETAILS_STAGE_ID_V1!r}",
        )

    details = _require_exact_array(root["details"], "$.details")
    if len(details) > MAX_SEMANTIC_DETAILS_V1:
        _fail(
            "too_many_semantic_details",
            "$.details",
            f"semantic-details stage supports at most {MAX_SEMANTIC_DETAILS_V1} details",
        )

    seen_ids: set[str] = set()
    for detail_index, detail_value in enumerate(details):
        detail_path = f"$.details[{detail_index}]"
        detail = _require_exact_object(detail_value, detail_path, _SEMANTIC_DETAIL_FIELDS)
        detail_id = _validate_detail_id(detail["id"], f"{detail_path}.id")
        if detail_id in seen_ids:
            _fail(
                "duplicate_semantic_detail_id",
                f"{detail_path}.id",
                f"duplicate semantic detail id {detail_id!r}",
            )
        seen_ids.add(detail_id)

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
            "semantic-details PixelProgram canvas must equal the S3 palette/light stage canvas",
        )

    operations = program["operations"]
    if len(details) != len(operations):
        _fail(
            "detail_operation_mismatch",
            "$.details",
            "details must map positionally one-to-one to PixelProgram operations",
        )

    palette_colors = {
        tuple(color["rgba"])
        for color in palette_stage["palette"]
    }

    for detail_index, operation in enumerate(operations):
        pixels = operation["pixels"]
        pixels_path = f"$.program.operations[{detail_index}].pixels"
        if not pixels:
            _fail(
                "empty_semantic_detail",
                pixels_path,
                f"semantic detail at index {detail_index} must contain at least one pixel edit",
            )
        if len(pixels) > MAX_PIXELS_PER_SEMANTIC_DETAIL_V1:
            _fail(
                "too_many_semantic_detail_pixels",
                pixels_path,
                "semantic detail exceeds the bounded raw-patch edit budget of "
                f"{MAX_PIXELS_PER_SEMANTIC_DETAIL_V1} pixels",
            )

        for pixel_index, pixel in enumerate(pixels):
            color = tuple(pixel[2:6])
            if color not in palette_colors:
                _fail(
                    "undeclared_palette_color",
                    f"{pixels_path}[{pixel_index}]",
                    "semantic-detail pixel color must exactly match a color declared by the S3 palette",
                )

    return cast(SemanticDetailsStageV1, stage)
