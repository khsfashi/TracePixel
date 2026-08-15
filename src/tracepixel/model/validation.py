from __future__ import annotations

from typing import cast

from tracepixel.raster.contract import (
    CanvasSizeError,
    CanvasSpec,
    ColorValueError,
    PixelCoordinateError,
    validate_rgba8,
)

from .pixel_ir import (
    PIXEL_PROGRAM_SCHEMA_V1,
    SET_PIXELS_OPERATION_V1,
    PixelProgramV1,
)


class PixelProgramValidationError(ValueError):
    """Deterministic PixelProgram rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise PixelProgramValidationError(code, path, message)


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


def validate_pixel_program(program: object) -> PixelProgramV1:
    """Validate a PixelProgram v1 without creating or mutating raster authority."""

    root = _require_exact_object(
        program,
        "$",
        frozenset(("schema", "canvas", "operations")),
    )

    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != PIXEL_PROGRAM_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {PIXEL_PROGRAM_SCHEMA_V1!r}",
        )

    canvas = _require_exact_object(
        root["canvas"],
        "$.canvas",
        frozenset(("width", "height")),
    )
    try:
        spec = CanvasSpec(canvas["width"], canvas["height"])
    except CanvasSizeError as exc:
        _fail("invalid_canvas", "$.canvas", str(exc))

    operations = _require_exact_array(root["operations"], "$.operations")
    for operation_index, operation_value in enumerate(operations):
        operation_path = f"$.operations[{operation_index}]"
        operation = _require_exact_object(
            operation_value,
            operation_path,
            frozenset(("op", "pixels")),
        )

        op = operation["op"]
        if type(op) is not str:
            _fail("invalid_type", f"{operation_path}.op", "must be a string")
        if op != SET_PIXELS_OPERATION_V1:
            _fail(
                "unsupported_operation",
                f"{operation_path}.op",
                f"unsupported operation {op!r}",
            )

        pixels = _require_exact_array(operation["pixels"], f"{operation_path}.pixels")
        for pixel_index, pixel_value in enumerate(pixels):
            pixel_path = f"{operation_path}.pixels[{pixel_index}]"
            pixel = _require_exact_array(pixel_value, pixel_path)
            if len(pixel) != 6:
                _fail(
                    "invalid_edit",
                    pixel_path,
                    "must contain exactly [x, y, r, g, b, a]",
                )

            x, y, r, g, b, a = pixel
            try:
                spec.offset(x, y)
            except PixelCoordinateError as exc:
                _fail("invalid_coordinate", pixel_path, str(exc))
            try:
                validate_rgba8((r, g, b, a))
            except ColorValueError as exc:
                _fail("invalid_color", pixel_path, str(exc))

    return cast(PixelProgramV1, program)
