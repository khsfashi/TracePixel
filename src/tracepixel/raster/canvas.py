from __future__ import annotations

import struct
from collections.abc import Sequence

from tracepixel.raster.contract import (
    RGBA8,
    CanvasSpec,
    RasterContractError,
    validate_rgba8,
)

_BATCH_EDIT_STRUCT = struct.Struct("<IBBBB")


class BatchEditError(RasterContractError):
    """Raised when a batch mutation does not have the required edit shape."""


class Canvas:
    """Owned deterministic RGBA8 raster with transactional pixel mutation."""

    __slots__ = ("_spec", "_pixels")

    def __init__(self, width: int, height: int) -> None:
        spec = CanvasSpec(width, height)
        self._spec = spec
        self._pixels = bytearray(spec.byte_length)

    @property
    def spec(self) -> CanvasSpec:
        return self._spec

    @property
    def width(self) -> int:
        return self._spec.width

    @property
    def height(self) -> int:
        return self._spec.height

    @property
    def byte_length(self) -> int:
        return self._spec.byte_length

    def get_pixel(self, x: object, y: object) -> RGBA8:
        offset = self._spec.offset(x, y)
        pixels = self._pixels
        return (
            pixels[offset],
            pixels[offset + 1],
            pixels[offset + 2],
            pixels[offset + 3],
        )

    def set_pixel(self, x: object, y: object, color: object) -> None:
        offset = self._spec.offset(x, y)
        validate_rgba8(color)
        self._write_rgba8(offset, color)

    def set_pixels(self, edits: object) -> None:
        staged = _stage_batch(self._spec, edits)
        pixels = self._pixels
        for offset, red, green, blue, alpha in _BATCH_EDIT_STRUCT.iter_unpack(staged):
            pixels[offset] = red
            pixels[offset + 1] = green
            pixels[offset + 2] = blue
            pixels[offset + 3] = alpha

    def rgba_bytes(self) -> bytes:
        """Return an owned exact snapshot of the authoritative row-major RGBA8 bytes."""
        return bytes(self._pixels)

    def _rgba_view(self) -> memoryview:
        """Borrow a read-only zero-copy view for synchronous package-internal operations."""
        return memoryview(self._pixels).toreadonly()

    def _write_rgba8(self, offset: int, color: Sequence[int]) -> None:
        pixels = self._pixels
        pixels[offset] = color[0]
        pixels[offset + 1] = color[1]
        pixels[offset + 2] = color[2]
        pixels[offset + 3] = color[3]


def _stage_batch(spec: CanvasSpec, edits: object) -> bytearray:
    if not isinstance(edits, Sequence) or isinstance(edits, (str, bytes, bytearray)):
        raise BatchEditError("pixel batch must be an ordered sequence of edits")

    staged = bytearray(len(edits) * _BATCH_EDIT_STRUCT.size)
    for index, edit in enumerate(edits):
        if not isinstance(edit, Sequence) or isinstance(edit, (str, bytes, bytearray)):
            raise BatchEditError("each pixel edit must be a three-item sequence")
        if len(edit) != 3:
            raise BatchEditError("each pixel edit must contain x, y, and RGBA8 color")

        x, y, color = edit
        offset = spec.offset(x, y)
        validate_rgba8(color)
        _BATCH_EDIT_STRUCT.pack_into(
            staged,
            index * _BATCH_EDIT_STRUCT.size,
            offset,
            color[0],
            color[1],
            color[2],
            color[3],
        )
    return staged
