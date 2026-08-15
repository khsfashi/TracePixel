from __future__ import annotations

from typing import cast

from .major_forms_stage import (
    MAJOR_FORMS_STAGE_ID_V1,
    MAJOR_FORMS_STAGE_SCHEMA_V1,
    MAX_MAJOR_FORMS_V1,
    MajorFormsStageV1,
)
from .validation import PixelProgramValidationError, validate_pixel_program

_MAJOR_FORMS_STAGE_FIELDS = frozenset(("schema", "stage", "forms", "program"))
_MAJOR_FORM_FIELDS = frozenset(("id",))
_MAJOR_FORM_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_-")


class MajorFormsStageValidationError(ValueError):
    """Deterministic P3-S2 rejection with a stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise MajorFormsStageValidationError(code, path, message)


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


def _validate_form_id(value: object, path: str) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    form_id = cast(str, value)
    if not 1 <= len(form_id) <= 32:
        _fail("invalid_form_id", path, "must contain 1..32 characters")
    if not "a" <= form_id[0] <= "z":
        _fail("invalid_form_id", path, "must start with lowercase ASCII a-z")
    if any(character not in _MAJOR_FORM_ID_CHARS for character in form_id):
        _fail(
            "invalid_form_id",
            path,
            "must contain only lowercase ASCII a-z, digits, '_' or '-'",
        )
    return form_id


def validate_major_forms_stage(stage: object) -> MajorFormsStageV1:
    """Validate bounded flat major forms without executing or copying raster state."""

    root = _require_exact_object(stage, "$", _MAJOR_FORMS_STAGE_FIELDS)

    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != MAJOR_FORMS_STAGE_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {MAJOR_FORMS_STAGE_SCHEMA_V1!r}",
        )

    stage_id = root["stage"]
    if type(stage_id) is not str:
        _fail("invalid_type", "$.stage", "must be a string")
    if stage_id != MAJOR_FORMS_STAGE_ID_V1:
        _fail(
            "invalid_stage",
            "$.stage",
            f"expected stage {MAJOR_FORMS_STAGE_ID_V1!r}",
        )

    forms = _require_exact_array(root["forms"], "$.forms")
    if not forms:
        _fail("empty_major_forms", "$.forms", "major-forms stage must contain at least one form")
    if len(forms) > MAX_MAJOR_FORMS_V1:
        _fail(
            "too_many_major_forms",
            "$.forms",
            f"major-forms stage supports at most {MAX_MAJOR_FORMS_V1} forms",
        )

    seen_ids: set[str] = set()
    for form_index, form_value in enumerate(forms):
        form_path = f"$.forms[{form_index}]"
        form = _require_exact_object(form_value, form_path, _MAJOR_FORM_FIELDS)
        form_id = _validate_form_id(form["id"], f"{form_path}.id")
        if form_id in seen_ids:
            _fail("duplicate_form_id", f"{form_path}.id", f"duplicate form id {form_id!r}")
        seen_ids.add(form_id)

    try:
        program = validate_pixel_program(root["program"])
    except PixelProgramValidationError as exc:
        _fail(
            "invalid_program",
            _program_path(exc.path),
            f"PixelProgram validation failed with {exc.code}: {exc.message}",
        )

    operations = program["operations"]
    if len(operations) != len(forms):
        _fail(
            "form_operation_mismatch",
            "$.forms",
            "forms and PixelProgram operations must have identical lengths and positional identity",
        )

    for form_index, operation in enumerate(operations):
        pixels = operation["pixels"]
        if not pixels:
            _fail(
                "empty_major_form",
                f"$.program.operations[{form_index}].pixels",
                f"major form at index {form_index} must contain at least one pixel edit",
            )

        first_color: tuple[int, int, int, int] | None = None
        for pixel_index, pixel in enumerate(pixels):
            r, g, b, a = pixel[2], pixel[3], pixel[4], pixel[5]
            pixel_path = f"$.program.operations[{form_index}].pixels[{pixel_index}]"

            if a != 255:
                _fail(
                    "invalid_major_form_alpha",
                    f"{pixel_path}[5]",
                    "major-form pixels must be fully opaque (alpha 255)",
                )

            color = (r, g, b, a)
            if first_color is None:
                first_color = color
            elif color != first_color:
                _fail(
                    "multiple_major_form_colors",
                    pixel_path,
                    "each P3-S2 major form must use one exact flat RGBA construction color",
                )

    return cast(MajorFormsStageV1, stage)
