from __future__ import annotations

from typing import cast

from .silhouette_stage import (
    SILHOUETTE_STAGE_ID_V1,
    SILHOUETTE_STAGE_SCHEMA_V1,
    SilhouetteStageV1,
)
from .validation import PixelProgramValidationError, validate_pixel_program

_SILHOUETTE_STAGE_FIELDS = frozenset(("schema", "stage", "program"))


class SilhouetteStageValidationError(ValueError):
    """Deterministic P3-S1 rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise SilhouetteStageValidationError(code, path, message)


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


def _program_path(path: str) -> str:
    if path == "$":
        return "$.program"
    if path.startswith("$"):
        return f"$.program{path[1:]}"
    return "$.program"


def validate_silhouette_stage(stage: object) -> SilhouetteStageV1:
    """Validate a flat, non-empty silhouette stage without executing raster state."""

    root = _require_exact_object(stage, "$", _SILHOUETTE_STAGE_FIELDS)

    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != SILHOUETTE_STAGE_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {SILHOUETTE_STAGE_SCHEMA_V1!r}",
        )

    stage_id = root["stage"]
    if type(stage_id) is not str:
        _fail("invalid_type", "$.stage", "must be a string")
    if stage_id != SILHOUETTE_STAGE_ID_V1:
        _fail(
            "invalid_stage",
            "$.stage",
            f"expected stage {SILHOUETTE_STAGE_ID_V1!r}",
        )

    try:
        program = validate_pixel_program(root["program"])
    except PixelProgramValidationError as exc:
        _fail(
            "invalid_program",
            _program_path(exc.path),
            f"PixelProgram validation failed with {exc.code}: {exc.message}",
        )

    first_color: tuple[int, int, int, int] | None = None
    edit_count = 0

    for operation_index, operation in enumerate(program["operations"]):
        for pixel_index, pixel in enumerate(operation["pixels"]):
            edit_count += 1
            r, g, b, a = pixel[2], pixel[3], pixel[4], pixel[5]
            pixel_path = f"$.program.operations[{operation_index}].pixels[{pixel_index}]"

            if a != 255:
                _fail(
                    "invalid_silhouette_alpha",
                    f"{pixel_path}[5]",
                    "silhouette pixels must be fully opaque (alpha 255)",
                )

            color = (r, g, b, a)
            if first_color is None:
                first_color = color
            elif color != first_color:
                _fail(
                    "multiple_silhouette_colors",
                    pixel_path,
                    "P3-S1 silhouette must use one exact flat RGBA color",
                )

    if edit_count == 0:
        _fail(
            "empty_silhouette",
            "$.program.operations",
            "silhouette stage must contain at least one pixel edit",
        )

    return cast(SilhouetteStageV1, stage)
