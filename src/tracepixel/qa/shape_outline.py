from __future__ import annotations

from typing import Literal, TypedDict

from tracepixel.raster import Canvas

SHAPE_OUTLINE_QA_SCHEMA_V1 = "tracepixel.shape-outline-qa.v1"

ShapeSymmetryAxisV1 = Literal["vertical", "horizontal", "both"]


class ShapeQaConfigurationError(ValueError):
    """Raised when optional Q3 analysis inputs are invalid."""


class AxisSymmetryFactsV1(TypedDict):
    matches: bool
    mismatched_pairs: int


class SymmetryCheckV1(TypedDict):
    requested: ShapeSymmetryAxisV1
    vertical: AxisSymmetryFactsV1 | None
    horizontal: AxisSymmetryFactsV1 | None


class VisibleAdjacencyFactsV1(TypedDict):
    horizontal: int
    vertical: int
    total: int


class ExposedEdgeFactsV1(TypedDict):
    top: int
    right: int
    bottom: int
    left: int
    total: int


class OutlineFactsV1(TypedDict):
    boundary_pixels: int
    interior_pixels: int
    visible_adjacencies: VisibleAdjacencyFactsV1
    exposed_edges: ExposedEdgeFactsV1


class ShapeOutlineQaV1(TypedDict):
    schema: Literal["tracepixel.shape-outline-qa.v1"]
    visible_pixels: int
    symmetry: SymmetryCheckV1 | None
    outline: OutlineFactsV1


def analyze_shape_outline(
    canvas: Canvas,
    *,
    required_symmetry: ShapeSymmetryAxisV1 | None = None,
) -> ShapeOutlineQaV1:
    """Return exact visibility-shape symmetry and finite outline facts.

    Structural visibility is alpha != 0. Symmetry is evaluated only when the caller
    explicitly supplies ``required_symmetry`` and compares the visibility mask across
    the full canvas center axis or axes. Outline diagnostics count exact 4-neighbor
    visible adjacencies and visible-to-empty/outside exposed pixel edges.

    The analyzer borrows Canvas' package-internal read-only RGBA view, performs one
    row-major O(width * height) scan and retains only scalar counters.
    """

    if not isinstance(canvas, Canvas):
        raise TypeError("canvas must be a tracepixel.raster.Canvas")
    if required_symmetry is not None and required_symmetry not in (
        "vertical",
        "horizontal",
        "both",
    ):
        raise ShapeQaConfigurationError(
            "required_symmetry must be one of: vertical, horizontal, both, or None"
        )

    width = canvas.width
    height = canvas.height
    rgba = canvas._rgba_view()

    visible_pixels = 0
    boundary_pixels = 0
    interior_pixels = 0

    horizontal_adjacencies = 0
    vertical_adjacencies = 0

    exposed_top = 0
    exposed_right = 0
    exposed_bottom = 0
    exposed_left = 0

    check_vertical = required_symmetry in ("vertical", "both")
    check_horizontal = required_symmetry in ("horizontal", "both")
    vertical_mismatched_pairs = 0
    horizontal_mismatched_pairs = 0

    for y in range(height):
        row_start = y * width
        for x in range(width):
            index = row_start + x
            alpha_offset = (index << 2) + 3
            is_visible = rgba[alpha_offset] != 0

            if check_vertical and x < width // 2:
                mirror_index = row_start + (width - 1 - x)
                mirror_visible = rgba[(mirror_index << 2) + 3] != 0
                if is_visible != mirror_visible:
                    vertical_mismatched_pairs += 1

            if check_horizontal and y < height // 2:
                mirror_index = (height - 1 - y) * width + x
                mirror_visible = rgba[(mirror_index << 2) + 3] != 0
                if is_visible != mirror_visible:
                    horizontal_mismatched_pairs += 1

            if not is_visible:
                continue

            visible_pixels += 1
            is_boundary = False

            if y == 0 or rgba[((index - width) << 2) + 3] == 0:
                exposed_top += 1
                is_boundary = True

            if x + 1 == width or rgba[((index + 1) << 2) + 3] == 0:
                exposed_right += 1
                is_boundary = True
            else:
                horizontal_adjacencies += 1

            if y + 1 == height or rgba[((index + width) << 2) + 3] == 0:
                exposed_bottom += 1
                is_boundary = True
            else:
                vertical_adjacencies += 1

            if x == 0 or rgba[((index - 1) << 2) + 3] == 0:
                exposed_left += 1
                is_boundary = True

            if is_boundary:
                boundary_pixels += 1
            else:
                interior_pixels += 1

    symmetry: SymmetryCheckV1 | None = None
    if required_symmetry is not None:
        vertical: AxisSymmetryFactsV1 | None = None
        horizontal: AxisSymmetryFactsV1 | None = None

        if check_vertical:
            vertical = {
                "matches": vertical_mismatched_pairs == 0,
                "mismatched_pairs": vertical_mismatched_pairs,
            }
        if check_horizontal:
            horizontal = {
                "matches": horizontal_mismatched_pairs == 0,
                "mismatched_pairs": horizontal_mismatched_pairs,
            }

        symmetry = {
            "requested": required_symmetry,
            "vertical": vertical,
            "horizontal": horizontal,
        }

    adjacency_total = horizontal_adjacencies + vertical_adjacencies
    exposed_total = exposed_top + exposed_right + exposed_bottom + exposed_left

    return {
        "schema": SHAPE_OUTLINE_QA_SCHEMA_V1,
        "visible_pixels": visible_pixels,
        "symmetry": symmetry,
        "outline": {
            "boundary_pixels": boundary_pixels,
            "interior_pixels": interior_pixels,
            "visible_adjacencies": {
                "horizontal": horizontal_adjacencies,
                "vertical": vertical_adjacencies,
                "total": adjacency_total,
            },
            "exposed_edges": {
                "top": exposed_top,
                "right": exposed_right,
                "bottom": exposed_bottom,
                "left": exposed_left,
                "total": exposed_total,
            },
        },
    }
