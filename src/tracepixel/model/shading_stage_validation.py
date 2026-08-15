from __future__ import annotations

from typing import cast

from .art_intent import ArtIntentV1
from .art_intent_validation import ArtIntentValidationError, validate_art_intent
from .palette_light_stage import PaletteLightStageV1
from .palette_light_stage_validation import (
    PaletteLightStageValidationError,
    validate_palette_light_stage,
)
from .shading_stage import (
    MAX_SHADING_APPLICATIONS_V1,
    SHADING_STAGE_ID_V1,
    SHADING_STAGE_SCHEMA_V1,
    ShadingStageV1,
)
from .validation import PixelProgramValidationError, validate_pixel_program

_SHADING_STAGE_FIELDS = frozenset(("schema", "stage", "applications", "program"))
_SHADING_APPLICATION_FIELDS = frozenset(
    ("id", "ramp_id", "source_role", "target_role", "relation")
)
_SHADING_RELATIONS = frozenset(("toward_light", "away_from_light"))
_SLUG_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")
_LIGHT_VECTORS: dict[str, tuple[int, int]] = {
    "top": (0, -1),
    "top_right": (1, -1),
    "right": (1, 0),
    "bottom_right": (1, 1),
    "bottom": (0, 1),
    "bottom_left": (-1, 1),
    "left": (-1, 0),
    "top_left": (-1, -1),
}


class ShadingStageValidationError(ValueError):
    """Deterministic P3-S4 rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise ShadingStageValidationError(code, path, message)


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


def _rebase_context(name: str, path: str) -> str:
    prefix = f"$context.{name}"
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


def _inside_bounds(x: int, y: int, bounds: dict[str, int]) -> bool:
    return (
        bounds["x"] <= x < bounds["x"] + bounds["width"]
        and bounds["y"] <= y < bounds["y"] + bounds["height"]
    )


def _light_projection(
    x: int,
    y: int,
    bounds: dict[str, int],
    light_direction: str,
) -> int:
    # Use doubled pixel-center and bounds-center coordinates so the test is exact integer math.
    pixel_x2 = 2 * x + 1
    pixel_y2 = 2 * y + 1
    center_x2 = 2 * bounds["x"] + bounds["width"]
    center_y2 = 2 * bounds["y"] + bounds["height"]
    vector_x, vector_y = _LIGHT_VECTORS[light_direction]
    return (pixel_x2 - center_x2) * vector_x + (pixel_y2 - center_y2) * vector_y


def validate_shading_stage(
    stage: object,
    *,
    art_intent: object,
    palette_light_stage: object,
) -> ShadingStageV1:
    """Validate bounded S4 shading against explicit S0 light intent and S3 ramp metadata."""

    root = _require_exact_object(stage, "$", _SHADING_STAGE_FIELDS)

    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != SHADING_STAGE_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {SHADING_STAGE_SCHEMA_V1!r}",
        )

    stage_id = root["stage"]
    if type(stage_id) is not str:
        _fail("invalid_type", "$.stage", "must be a string")
    if stage_id != SHADING_STAGE_ID_V1:
        _fail("invalid_stage", "$.stage", f"expected stage {SHADING_STAGE_ID_V1!r}")

    applications = _require_exact_array(root["applications"], "$.applications")
    if len(applications) > MAX_SHADING_APPLICATIONS_V1:
        _fail(
            "too_many_shading_applications",
            "$.applications",
            f"shading stage supports at most {MAX_SHADING_APPLICATIONS_V1} applications",
        )

    try:
        intent = validate_art_intent(art_intent)
    except ArtIntentValidationError as exc:
        _fail(
            "invalid_art_intent",
            _rebase_context("art_intent", exc.path),
            f"ArtIntent validation failed with {exc.code}: {exc.message}",
        )

    try:
        palette_stage = validate_palette_light_stage(palette_light_stage)
    except PaletteLightStageValidationError as exc:
        _fail(
            "invalid_palette_light_stage",
            _rebase_context("palette_light_stage", exc.path),
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

    intent = cast(ArtIntentV1, intent)
    palette_stage = cast(PaletteLightStageV1, palette_stage)

    if program["canvas"] != intent["canvas"]:
        _fail(
            "canvas_mismatch",
            "$.program.canvas",
            "shading PixelProgram canvas must equal ArtIntent canvas",
        )
    if palette_stage["program"]["canvas"] != intent["canvas"]:
        _fail(
            "context_canvas_mismatch",
            "$context.palette_light_stage.program.canvas",
            "palette/light stage canvas must equal ArtIntent canvas",
        )

    operations = program["operations"]
    if len(applications) != len(operations):
        _fail(
            "application_operation_mismatch",
            "$.applications",
            "applications must map positionally one-to-one to PixelProgram operations",
        )

    light_direction = intent["composition"]["light_direction"]
    occupied_bounds_value = intent["composition"]["occupied_bounds"]
    if applications and light_direction is None:
        _fail(
            "missing_light_direction",
            "$context.art_intent.composition.light_direction",
            "non-empty shading requires explicit ArtIntent light_direction",
        )
    if applications and occupied_bounds_value is None:
        _fail(
            "missing_occupied_bounds",
            "$context.art_intent.composition.occupied_bounds",
            "non-empty shading requires explicit occupied_bounds for deterministic light-side geometry",
        )

    palette_by_role = {
        color["role"]: tuple(color["rgba"])
        for color in palette_stage["palette"]
    }
    ramps_by_id = {ramp["id"]: ramp["colors"] for ramp in palette_stage["ramps"]}

    bounds = cast(dict[str, int] | None, occupied_bounds_value)
    direction = cast(str | None, light_direction)
    application_ids: set[str] = set()

    for application_index, application_value in enumerate(applications):
        application_path = f"$.applications[{application_index}]"
        application = _require_exact_object(
            application_value,
            application_path,
            _SHADING_APPLICATION_FIELDS,
        )

        application_id = _validate_slug(
            application["id"],
            f"{application_path}.id",
            "invalid_shading_application_id",
            "shading application id",
        )
        if application_id in application_ids:
            _fail(
                "duplicate_shading_application_id",
                f"{application_path}.id",
                f"duplicate shading application id {application_id!r}",
            )
        application_ids.add(application_id)

        ramp_id = _validate_slug(
            application["ramp_id"],
            f"{application_path}.ramp_id",
            "invalid_light_ramp_id",
            "light-ramp id",
        )
        ramp_roles = ramps_by_id.get(ramp_id)
        if ramp_roles is None:
            _fail(
                "unknown_light_ramp",
                f"{application_path}.ramp_id",
                f"unknown light-ramp id {ramp_id!r}",
            )

        source_role = _validate_slug(
            application["source_role"],
            f"{application_path}.source_role",
            "invalid_palette_role",
            "source palette role",
        )
        target_role = _validate_slug(
            application["target_role"],
            f"{application_path}.target_role",
            "invalid_palette_role",
            "target palette role",
        )
        if source_role not in ramp_roles:
            _fail(
                "source_role_not_in_ramp",
                f"{application_path}.source_role",
                f"palette role {source_role!r} is not in light ramp {ramp_id!r}",
            )
        if target_role not in ramp_roles:
            _fail(
                "target_role_not_in_ramp",
                f"{application_path}.target_role",
                f"palette role {target_role!r} is not in light ramp {ramp_id!r}",
            )

        relation_value = application["relation"]
        if type(relation_value) is not str:
            _fail("invalid_type", f"{application_path}.relation", "must be a string")
        relation = cast(str, relation_value)
        if relation not in _SHADING_RELATIONS:
            _fail(
                "invalid_shading_relation",
                f"{application_path}.relation",
                f"unsupported shading relation {relation!r}",
            )

        source_index = ramp_roles.index(source_role)
        target_index = ramp_roles.index(target_role)
        if relation == "toward_light" and target_index <= source_index:
            _fail(
                "invalid_ramp_transition",
                f"{application_path}.target_role",
                "toward_light must move forward in the authored light-ramp order",
            )
        if relation == "away_from_light" and target_index >= source_index:
            _fail(
                "invalid_ramp_transition",
                f"{application_path}.target_role",
                "away_from_light must move backward in the authored light-ramp order",
            )

        source_rgba = palette_by_role[source_role]
        target_rgba = palette_by_role[target_role]
        if source_rgba[3] != target_rgba[3]:
            _fail(
                "alpha_change",
                f"{application_path}.target_role",
                "shading transitions must preserve authored alpha",
            )

        operation = operations[application_index]
        pixels = operation["pixels"]
        if not pixels:
            _fail(
                "empty_shading_application",
                f"$.program.operations[{application_index}].pixels",
                "a shading application must edit at least one pixel",
            )

        assert bounds is not None
        assert direction is not None
        for pixel_index, pixel in enumerate(pixels):
            pixel_path = f"$.program.operations[{application_index}].pixels[{pixel_index}]"
            rgba = (pixel[2], pixel[3], pixel[4], pixel[5])
            if rgba != target_rgba:
                _fail(
                    "target_color_mismatch",
                    pixel_path,
                    f"pixel color {rgba!r} must equal target role {target_role!r} color {target_rgba!r}",
                )

            x, y = pixel[0], pixel[1]
            if not _inside_bounds(x, y, bounds):
                _fail(
                    "outside_occupied_bounds",
                    pixel_path,
                    "shading pixel must lie inside ArtIntent occupied_bounds",
                )

            projection = _light_projection(x, y, bounds, direction)
            if relation == "toward_light" and projection < 0:
                _fail(
                    "wrong_light_side",
                    pixel_path,
                    "toward_light pixel lies on the away-from-light half-plane",
                )
            if relation == "away_from_light" and projection > 0:
                _fail(
                    "wrong_light_side",
                    pixel_path,
                    "away_from_light pixel lies on the toward-light half-plane",
                )

    return cast(ShadingStageV1, stage)
