from __future__ import annotations

from collections.abc import Sequence

from tracepixel.raster import Canvas

from .pixel_ir import PixelEditV1
from .validation import validate_pixel_program

PixelMutation = tuple[int, int, tuple[int, int, int, int]]


class _ValidatedPixelBatch(Sequence[PixelMutation]):
    """Lazy adapter from validated serialized edits to the P1 batch surface."""

    __slots__ = ("_pixels",)

    def __init__(self, pixels: list[PixelEditV1]) -> None:
        self._pixels = pixels

    def __len__(self) -> int:
        return len(self._pixels)

    def __getitem__(self, index: int | slice) -> PixelMutation | list[PixelMutation]:
        if isinstance(index, slice):
            return [self._mutation_at(i) for i in range(*index.indices(len(self)))]
        return self._mutation_at(index)

    def _mutation_at(self, index: int) -> PixelMutation:
        x, y, red, green, blue, alpha = self._pixels[index]
        return x, y, (red, green, blue, alpha)


def execute_pixel_program(program: object) -> Canvas:
    """Validate and deterministically execute one PixelProgram v1 into a fresh Canvas."""

    validated = validate_pixel_program(program)
    canvas_document = validated["canvas"]
    canvas = Canvas(canvas_document["width"], canvas_document["height"])

    for operation in validated["operations"]:
        canvas.set_pixels(_ValidatedPixelBatch(operation["pixels"]))

    return canvas
