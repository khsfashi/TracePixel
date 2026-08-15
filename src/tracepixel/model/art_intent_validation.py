from __future__ import annotations

from typing import cast

from tracepixel.raster.contract import CanvasSizeError, CanvasSpec

from .art_intent import ART_INTENT_SCHEMA_V1, ArtIntentV1

_ART_INTENT_FIELDS = frozenset(("schema", "asset_class", "canvas", "composition"))
_CANVAS_FIELDS = frozenset(("width", "height"))
_COMPOSITION_FIELDS = frozenset(
    ("occupied_bounds", "facing", "symmetry", "light_direction", "palette_budget")
)
_BOUNDS_FIELDS = frozenset(("x", "y", "width", "height"))
_SYMMETRY_FIELDS = frozenset(("axis", "strength"))

_FACING_VALUES = frozenset(("left", "right", "up", "down", "front", "back"))
_LIGHT_DIRECTION_VALUES = frozenset(
    (
        "top",
        "top_right",
        "right",
        "bottom_right",
        "bottom",
        "bottom_left",
        "left",
        "top_left",
    )
)
_SYMMETRY_AXIS_VALUES = frozenset(("vertical", "horizontal", "both"))
_SYMMETRY_STRENGTH_VALUES = frozenset(("hint", "required"))


class ArtIntentValidationError(ValueError):
    """Deterministic ArtIntent rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise ArtIntentValidationError(code, path, message)


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


def _require_nullable_enum(
    value: object,
    path: str,
    allowed: frozenset[str],
) -> None:
    if value is None:
        return
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string or null")
    if value not in allowed:
        _fail("invalid_value", path, f"unsupported value {value!r}")


def _validate_bounds(value: object, path: str, spec: CanvasSpec) -> None:
    if value is None:
        return

    bounds = _require_exact_object(value, path, _BOUNDS_FIELDS)
    x = bounds["x"]
    y = bounds["y"]
    width = bounds["width"]
    height = bounds["height"]

    if not all(type(part) is int for part in (x, y, width, height)):
        _fail("invalid_bounds", path, "x, y, width and height must be exact integers")
    assert type(x) is int
    assert type(y) is int
    assert type(width) is int
    assert type(height) is int

    if x < 0 or y < 0 or width < 1 or height < 1:
        _fail(
            "invalid_bounds",
            path,
            "x/y must be non-negative and width/height must be positive",
        )
    if x + width > spec.width or y + height > spec.height:
        _fail("invalid_bounds", path, "occupied bounds must fit inside the canvas")


def _validate_symmetry(value: object, path: str) -> None:
    if value is None:
        return

    symmetry = _require_exact_object(value, path, _SYMMETRY_FIELDS)
    axis = symmetry["axis"]
    strength = symmetry["strength"]

    if type(axis) is not str:
        _fail("invalid_type", f"{path}.axis", "must be a string")
    if axis not in _SYMMETRY_AXIS_VALUES:
        _fail("invalid_value", f"{path}.axis", f"unsupported symmetry axis {axis!r}")

    if type(strength) is not str:
        _fail("invalid_type", f"{path}.strength", "must be a string")
    if strength not in _SYMMETRY_STRENGTH_VALUES:
        _fail(
            "invalid_value",
            f"{path}.strength",
            f"unsupported symmetry strength {strength!r}",
        )


def validate_art_intent(intent: object) -> ArtIntentV1:
    """Validate ArtIntent v1 without creating raster authority or stage state."""

    root = _require_exact_object(intent, "$", _ART_INTENT_FIELDS)

    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != ART_INTENT_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {ART_INTENT_SCHEMA_V1!r}",
        )

    asset_class = root["asset_class"]
    if type(asset_class) is not str:
        _fail("invalid_type", "$.asset_class", "must be a string")
    if not 1 <= len(asset_class) <= 64:
        _fail("invalid_asset_class", "$.asset_class", "length must be in [1, 64]")

    canvas = _require_exact_object(root["canvas"], "$.canvas", _CANVAS_FIELDS)
    try:
        spec = CanvasSpec(canvas["width"], canvas["height"])
    except CanvasSizeError as exc:
        _fail("invalid_canvas", "$.canvas", str(exc))

    composition = _require_exact_object(
        root["composition"],
        "$.composition",
        _COMPOSITION_FIELDS,
    )
    _validate_bounds(composition["occupied_bounds"], "$.composition.occupied_bounds", spec)
    _require_nullable_enum(composition["facing"], "$.composition.facing", _FACING_VALUES)
    _validate_symmetry(composition["symmetry"], "$.composition.symmetry")
    _require_nullable_enum(
        composition["light_direction"],
        "$.composition.light_direction",
        _LIGHT_DIRECTION_VALUES,
    )

    palette_budget = composition["palette_budget"]
    if palette_budget is not None:
        if type(palette_budget) is not int or not 1 <= palette_budget <= 256:
            _fail(
                "invalid_palette_budget",
                "$.composition.palette_budget",
                "must be an exact integer in [1, 256] or null",
            )

    return cast(ArtIntentV1, intent)
