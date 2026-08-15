from __future__ import annotations

import json
from typing import cast

from .pixel_ir import PixelProgramV1
from .validation import validate_pixel_program


class PixelProgramSerializationError(ValueError):
    """Deterministic failure while decoding serialized PixelProgram JSON."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{message} [{code}]")


def serialize_pixel_program(program: object) -> bytes:
    """Validate and encode one PixelProgram v1 as canonical UTF-8 JSON bytes."""

    validated = validate_pixel_program(program)
    return json.dumps(
        validated,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def deserialize_pixel_program(payload: object) -> PixelProgramV1:
    """Decode UTF-8 JSON bytes and validate the resulting PixelProgram v1."""

    if type(payload) is not bytes:
        raise PixelProgramSerializationError(
            "invalid_type",
            "serialized PixelProgram must be bytes",
        )

    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PixelProgramSerializationError(
            "invalid_json",
            "serialized PixelProgram must be valid UTF-8 JSON",
        ) from exc

    return cast(PixelProgramV1, validate_pixel_program(decoded))
