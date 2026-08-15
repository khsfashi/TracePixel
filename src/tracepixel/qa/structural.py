from __future__ import annotations

from typing import Literal, TypedDict, cast

from tracepixel.raster import Canvas

STRUCTURAL_QA_SCHEMA_V1 = "tracepixel.structural-qa.v1"


class DimensionsV1(TypedDict):
    width: int
    height: int


class BoundsV1(TypedDict):
    x: int
    y: int
    width: int
    height: int


class MarginsV1(TypedDict):
    left: int
    top: int
    right: int
    bottom: int


class EdgeContactV1(TypedDict):
    left: bool
    top: bool
    right: bool
    bottom: bool
    any: bool


class AlphaFactsV1(TypedDict):
    transparent_pixels: int
    translucent_pixels: int
    opaque_pixels: int
    has_translucency: bool


class StructuralFactsV1(TypedDict):
    schema: Literal["tracepixel.structural-qa.v1"]
    dimensions: DimensionsV1
    empty: bool
    visible_pixels: int
    occupied_bounds: BoundsV1 | None
    margins: MarginsV1 | None
    edge_contact: EdgeContactV1
    alpha: AlphaFactsV1


def analyze_structural(canvas: Canvas) -> StructuralFactsV1:
    """Return exact raster-structural facts without applying policy or aesthetics.

    A pixel is structurally visible iff its stored alpha byte is non-zero. RGB bytes under
    alpha zero are intentionally ignored here; transparent-RGB policy belongs to P4-Q1.
    The scan borrows Canvas' package-internal read-only RGBA view, so it does not allocate
    an owned full-raster snapshot or a per-pixel object graph.
    """

    if not isinstance(canvas, Canvas):
        raise TypeError("canvas must be a tracepixel.raster.Canvas")

    width = canvas.width
    height = canvas.height
    rgba = canvas._rgba_view()

    transparent_pixels = 0
    translucent_pixels = 0
    opaque_pixels = 0
    visible_pixels = 0

    min_x = width
    min_y = height
    max_x = -1
    max_y = -1

    touches_left = False
    touches_top = False
    touches_right = False
    touches_bottom = False

    alpha_offset = 3
    for y in range(height):
        for x in range(width):
            alpha = rgba[alpha_offset]
            alpha_offset += 4

            if alpha == 0:
                transparent_pixels += 1
                continue

            visible_pixels += 1
            if alpha == 255:
                opaque_pixels += 1
            else:
                translucent_pixels += 1

            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y
            if x > max_x:
                max_x = x
            if y > max_y:
                max_y = y

            if x == 0:
                touches_left = True
            if y == 0:
                touches_top = True
            if x == width - 1:
                touches_right = True
            if y == height - 1:
                touches_bottom = True

    occupied_bounds: BoundsV1 | None
    margins: MarginsV1 | None
    if visible_pixels == 0:
        occupied_bounds = None
        margins = None
    else:
        occupied_bounds = {
            "x": min_x,
            "y": min_y,
            "width": max_x - min_x + 1,
            "height": max_y - min_y + 1,
        }
        margins = {
            "left": min_x,
            "top": min_y,
            "right": width - 1 - max_x,
            "bottom": height - 1 - max_y,
        }

    facts: StructuralFactsV1 = {
        "schema": STRUCTURAL_QA_SCHEMA_V1,
        "dimensions": {"width": width, "height": height},
        "empty": visible_pixels == 0,
        "visible_pixels": visible_pixels,
        "occupied_bounds": occupied_bounds,
        "margins": margins,
        "edge_contact": {
            "left": touches_left,
            "top": touches_top,
            "right": touches_right,
            "bottom": touches_bottom,
            "any": touches_left or touches_top or touches_right or touches_bottom,
        },
        "alpha": {
            "transparent_pixels": transparent_pixels,
            "translucent_pixels": translucent_pixels,
            "opaque_pixels": opaque_pixels,
            "has_translucency": translucent_pixels > 0,
        },
    }
    return cast(StructuralFactsV1, facts)
