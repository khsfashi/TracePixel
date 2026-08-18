from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

BYTES_PER_PIXEL = 4
MAX_CANVAS_DIMENSION = 4096
MAX_CANVAS_PIXELS = MAX_CANVAS_DIMENSION * MAX_CANVAS_DIMENSION
MAX_CANVAS_BYTES = MAX_CANVAS_PIXELS * BYTES_PER_PIXEL

RGBA8 = tuple[int, int, int, int]


class RasterContractError(ValueError):
    """Base class for deterministic raster contract violations."""


class CanvasSizeError(RasterContractError):
    """Raised when requested canvas dimensions violate the raster contract."""


class RasterByteDataError(RasterContractError):
    """Raised when authoritative RGBA8 byte data violates the raster contract."""


class PixelCoordinateError(RasterContractError):
    """Raised when a pixel coordinate is not an in-bounds integer coordinate."""


class ColorValueError(RasterContractError):
    """Raised when a color is not exact straight-alpha RGBA8."""


def _is_exact_int(value: object) -> bool:
    return type(value) is int


def validate_dimensions(width: object, height: object) -> None:
    if not _is_exact_int(width) or not _is_exact_int(height):
        raise CanvasSizeError("canvas width and height must be exact integers")
    if width < 1 or height < 1:
        raise CanvasSizeError("canvas width and height must be positive")
    if width > MAX_CANVAS_DIMENSION or height > MAX_CANVAS_DIMENSION:
        raise CanvasSizeError(
            f"canvas dimensions must be <= {MAX_CANVAS_DIMENSION} per axis"
        )

    pixels = width * height
    if pixels > MAX_CANVAS_PIXELS:
        raise CanvasSizeError(f"canvas pixel count must be <= {MAX_CANVAS_PIXELS}")
    if pixels * BYTES_PER_PIXEL > MAX_CANVAS_BYTES:
        raise CanvasSizeError(
            f"authoritative RGBA8 storage must be <= {MAX_CANVAS_BYTES} bytes"
        )


def _validate_coordinate(width: int, height: int, x: object, y: object) -> None:
    if not _is_exact_int(x) or not _is_exact_int(y):
        raise PixelCoordinateError("pixel x and y must be exact integers")
    if x < 0 or y < 0 or x >= width or y >= height:
        raise PixelCoordinateError(
            f"pixel coordinate ({x}, {y}) is outside [0,{width}) x [0,{height})"
        )


def validate_rgba8(color: object) -> None:
    if not isinstance(color, Sequence) or isinstance(color, (str, bytes, bytearray)):
        raise ColorValueError("color must be a four-channel RGBA8 sequence")
    if len(color) != 4:
        raise ColorValueError("color must contain exactly four RGBA8 channels")
    for channel in color:
        if not _is_exact_int(channel) or channel < 0 or channel > 255:
            raise ColorValueError("RGBA8 channels must be exact integers in [0, 255]")


@dataclass(frozen=True, slots=True)
class CanvasSpec:
    """Validated immutable layout metadata shared by raster implementations."""

    width: int
    height: int

    def __post_init__(self) -> None:
        validate_dimensions(self.width, self.height)

    @property
    def row_stride(self) -> int:
        return self.width * BYTES_PER_PIXEL

    @property
    def byte_length(self) -> int:
        return self.width * self.height * BYTES_PER_PIXEL

    def contains(self, x: object, y: object) -> bool:
        return (
            _is_exact_int(x)
            and _is_exact_int(y)
            and 0 <= x < self.width
            and 0 <= y < self.height
        )

    def offset(self, x: object, y: object) -> int:
        _validate_coordinate(self.width, self.height, x, y)
        return (y * self.width + x) * BYTES_PER_PIXEL
