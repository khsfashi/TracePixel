from __future__ import annotations

from typing import cast

from tracepixel.raster.contract import ColorValueError, validate_rgba8

from .palette_light_stage import (
    MAX_LIGHT_RAMPS_V1,
    MAX_PALETTE_COLORS_V1,
    PALETTE_LIGHT_STAGE_ID_V1,
    PALETTE_LIGHT_STAGE_SCHEMA_V1,
    PaletteLightStageV1,
)
from .validation import PixelProgramValidationError, validate_pixel_program

_PALETTE_LIGHT_STAGE_FIELDS = frozenset(("schema", "stage", "palette", "ramps", "program"))
_PALETTE_COLOR_FIELDS = frozenset(("role", "rgba"))
_LIGHT_RAMP_FIELDS = frozenset(("id", "colors"))
_SLUG_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")


class PaletteLightStageValidationError(ValueError):
    """Deterministic P3-S3 rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise PaletteLightStageValidationError(code, path, message)


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


def _program_path(path: str) -> str:
    if path == "$":
        return "$.program"
    if path.startswith("$"):
        return f"$.program{path[1:]}"
    return "$.program"


def _validate_slug(value: object, path: str, code: str, label: str) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    slug = cast(str, value)
    if not 1 <= len(slug) <= 32:
        _fail(code, path, f"{label} must contain 1..32 characters")
    if not "a" <= slug[0] <= "z":
        _fail(code, path, f"{label} must start with lowercase ASCII a-z")
    if any(character not in _SLUG_CHARS for character in slug):
        _fail(
            code,
            path,
            f"{label} must contain only lowercase ASCII a-z, digits, '_' or '-'",
        )
    return slug


def validate_palette_light_stage(stage: object) -> PaletteLightStageV1:
    """Validate authored palette membership and light-ramp references without raster execution."""

    root = _require_exact_object(stage, "$", _PALETTE_LIGHT_STAGE_FIELDS)

    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != PALETTE_LIGHT_STAGE_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {PALETTE_LIGHT_STAGE_SCHEMA_V1!r}",
        )

    stage_id = root["stage"]
    if type(stage_id) is not str:
        _fail("invalid_type", "$.stage", "must be a string")
    if stage_id != PALETTE_LIGHT_STAGE_ID_V1:
        _fail(
            "invalid_stage",
            "$.stage",
            f"expected stage {PALETTE_LIGHT_STAGE_ID_V1!r}",
        )

    palette = _require_exact_array(root["palette"], "$.palette")
    if not palette:
        _fail("empty_palette", "$.palette", "palette/light stage must declare at least one color")
    if len(palette) > MAX_PALETTE_COLORS_V1:
        _fail(
            "too_many_palette_colors",
            "$.palette",
            f"palette/light stage supports at most {MAX_PALETTE_COLORS_V1} colors",
        )

    palette_roles: set[str] = set()
    palette_colors: set[tuple[int, int, int, int]] = set()
    for color_index, color_value in enumerate(palette):
        color_path = f"$.palette[{color_index}]"
        color = _require_exact_object(color_value, color_path, _PALETTE_COLOR_FIELDS)

        role = _validate_slug(
            color["role"],
            f"{color_path}.role",
            "invalid_palette_role",
            "palette role",
        )
        if role in palette_roles:
            _fail(
                "duplicate_palette_role",
                f"{color_path}.role",
                f"duplicate palette role {role!r}",
            )

        rgba_value = _require_exact_array(color["rgba"], f"{color_path}.rgba")
        try:
            validate_rgba8(rgba_value)
        except ColorValueError as exc:
            _fail("invalid_palette_color", f"{color_path}.rgba", str(exc))
        rgba = cast(tuple[int, int, int, int], tuple(rgba_value))
        if rgba in palette_colors:
            _fail(
                "duplicate_palette_color",
                f"{color_path}.rgba",
                f"duplicate exact RGBA color {rgba!r}",
            )

        palette_roles.add(role)
        palette_colors.add(rgba)

    ramps = _require_exact_array(root["ramps"], "$.ramps")
    if len(ramps) > MAX_LIGHT_RAMPS_V1:
        _fail(
            "too_many_light_ramps",
            "$.ramps",
            f"palette/light stage supports at most {MAX_LIGHT_RAMPS_V1} ramps",
        )

    ramp_ids: set[str] = set()
    for ramp_index, ramp_value in enumerate(ramps):
        ramp_path = f"$.ramps[{ramp_index}]"
        ramp = _require_exact_object(ramp_value, ramp_path, _LIGHT_RAMP_FIELDS)

        ramp_id = _validate_slug(
            ramp["id"],
            f"{ramp_path}.id",
            "invalid_light_ramp_id",
            "light-ramp id",
        )
        if ramp_id in ramp_ids:
            _fail(
                "duplicate_light_ramp_id",
                f"{ramp_path}.id",
                f"duplicate light-ramp id {ramp_id!r}",
            )
        ramp_ids.add(ramp_id)

        colors = _require_exact_array(ramp["colors"], f"{ramp_path}.colors")
        if len(colors) < 2:
            _fail(
                "short_light_ramp",
                f"{ramp_path}.colors",
                "light ramp must reference at least two palette roles",
            )
        if len(colors) > MAX_PALETTE_COLORS_V1:
            _fail(
                "too_many_light_ramp_colors",
                f"{ramp_path}.colors",
                f"light ramp supports at most {MAX_PALETTE_COLORS_V1} role references",
            )

        seen_roles: set[str] = set()
        for color_index, role_value in enumerate(colors):
            role_path = f"{ramp_path}.colors[{color_index}]"
            if type(role_value) is not str:
                _fail("invalid_type", role_path, "must be a string")
            role = cast(str, role_value)
            if role not in palette_roles:
                _fail(
                    "unknown_palette_role",
                    role_path,
                    f"unknown palette role {role!r}",
                )
            if role in seen_roles:
                _fail(
                    "duplicate_light_ramp_role",
                    role_path,
                    f"light ramp repeats palette role {role!r}",
                )
            seen_roles.add(role)

    try:
        program = validate_pixel_program(root["program"])
    except PixelProgramValidationError as exc:
        _fail(
            "invalid_program",
            _program_path(exc.path),
            f"PixelProgram validation failed with {exc.code}: {exc.message}",
        )

    for operation_index, operation in enumerate(program["operations"]):
        for pixel_index, pixel in enumerate(operation["pixels"]):
            rgba = (pixel[2], pixel[3], pixel[4], pixel[5])
            if rgba not in palette_colors:
                _fail(
                    "undeclared_palette_color",
                    f"$.program.operations[{operation_index}].pixels[{pixel_index}]",
                    f"pixel color {rgba!r} is not declared in $.palette",
                )

    return cast(PaletteLightStageV1, stage)
