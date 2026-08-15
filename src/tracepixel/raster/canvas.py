from __future__ import annotations

from collections.abc import Sequence

from tracepixel.raster.contract import (
    RGBA8,
    CanvasSpec,
    RasterContractError,
    validate_rgba8,
)


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
        batch = _validate_batch_shape(edits)
        offsets = [self._spec.offset(x, y) for x, y, _ in batch]

        colors: list[RGBA8] = []
        for _, _, color in batch:
            validate_rgba8(color)
            colors.append((color[0], color[1], color[2], color[3]))

        for offset, color in zip(offsets, colors, strict=True):
            self._write_rgba8(offset, color)

    def _write_rgba8(self, offset: int, color: Sequence[int]) -> None:
        pixels = self._pixels
        pixels[offset] = color[0]
        pixels[offset + 1] = color[1]
        pixels[offset + 2] = color[2]
        pixels[offset + 3] = color[3]


def _validate_batch_shape(edits: object) -> list[tuple[object, object, Sequence[int]]]:
    if not isinstance(edits, Sequence) or isinstance(edits, (str, bytes, bytearray)):
        raise BatchEditError("pixel batch must be an ordered sequence of edits")

    batch: list[tuple[object, object, Sequence[int]]] = []
    for edit in edits:
        if not isinstance(edit, Sequence) or isinstance(edit, (str, bytes, bytearray)):
            raise BatchEditError("each pixel edit must be a three-item sequence")
        if len(edit) != 3:
            raise BatchEditError("each pixel edit must contain x, y, and RGBA8 color")
        x, y, color = edit
        batch.append((x, y, color))
    return batch
