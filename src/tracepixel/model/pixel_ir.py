from __future__ import annotations

from typing import Literal, TypedDict

PIXEL_PROGRAM_SCHEMA_V1 = "tracepixel.pixel-program.v1"
SET_PIXELS_OPERATION_V1 = "set_pixels"


class CanvasDocumentV1(TypedDict):
    """JSON-compatible canvas declaration for PixelProgram v1."""

    width: int
    height: int


PixelEditV1 = list[int]
"""Serialized pixel edit `[x, y, r, g, b, a]`; validated in P2-IR1."""


class SetPixelsOperationV1(TypedDict):
    """Ordered exact-pixel batch operation for PixelProgram v1."""

    op: Literal["set_pixels"]
    pixels: list[PixelEditV1]


class PixelProgramV1(TypedDict):
    """Versioned JSON-compatible program envelope frozen by P2-IR0."""

    schema: Literal["tracepixel.pixel-program.v1"]
    canvas: CanvasDocumentV1
    operations: list[SetPixelsOperationV1]
