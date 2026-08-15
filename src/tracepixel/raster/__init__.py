"""Deterministic raster authority surfaces."""

from tracepixel.raster.canvas import BatchEditError, Canvas
from tracepixel.raster.contract import (
    BYTES_PER_PIXEL,
    MAX_CANVAS_BYTES,
    MAX_CANVAS_DIMENSION,
    MAX_CANVAS_PIXELS,
    RGBA8,
    CanvasSizeError,
    CanvasSpec,
    ColorValueError,
    PixelCoordinateError,
    RasterContractError,
    validate_dimensions,
    validate_rgba8,
)
from tracepixel.raster.export import (
    ExportScaleError,
    PngExport,
    PngExportMetadata,
    export_native_png,
    export_nearest_preview_png,
)

__all__ = [
    "BYTES_PER_PIXEL",
    "MAX_CANVAS_BYTES",
    "MAX_CANVAS_DIMENSION",
    "MAX_CANVAS_PIXELS",
    "RGBA8",
    "BatchEditError",
    "Canvas",
    "CanvasSizeError",
    "CanvasSpec",
    "ColorValueError",
    "ExportScaleError",
    "PixelCoordinateError",
    "PngExport",
    "PngExportMetadata",
    "RasterContractError",
    "export_native_png",
    "export_nearest_preview_png",
    "validate_dimensions",
    "validate_rgba8",
]
