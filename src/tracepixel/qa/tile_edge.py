from __future__ import annotations

from typing import Literal, TypedDict, cast

from tracepixel.raster import Canvas

TILE_EDGE_QA_SCHEMA_V1 = "tracepixel.tile-edge-qa.v1"

TileEdgeRequirementV1 = Literal["left_right", "top_bottom", "both"]


class TileEdgeQaConfigurationError(ValueError):
    """Raised when explicit P4-Q4 tile-edge contract inputs are invalid."""


class EdgeEqualityFactsV1(TypedDict):
    compared_positions: int
    mismatched_positions: int
    matches: bool


class CornerEqualityFactsV1(TypedDict):
    all_equal: bool
    distinct_rgba_colors: int


class TileEdgeContractCheckV1(TypedDict):
    required_edges: TileEdgeRequirementV1 | None
    require_equal_corners: bool
    satisfied: bool


class TileEdgeQaV1(TypedDict):
    schema: Literal["tracepixel.tile-edge-qa.v1"]
    left_right: EdgeEqualityFactsV1
    top_bottom: EdgeEqualityFactsV1
    corners: CornerEqualityFactsV1
    contract: TileEdgeContractCheckV1 | None


def _pixel_equal(rgba: memoryview, first_index: int, second_index: int) -> bool:
    first = first_index << 2
    second = second_index << 2
    return (
        rgba[first] == rgba[second]
        and rgba[first + 1] == rgba[second + 1]
        and rgba[first + 2] == rgba[second + 2]
        and rgba[first + 3] == rgba[second + 3]
    )


def _packed_rgba(rgba: memoryview, pixel_index: int) -> int:
    offset = pixel_index << 2
    return (
        (rgba[offset] << 24)
        | (rgba[offset + 1] << 16)
        | (rgba[offset + 2] << 8)
        | rgba[offset + 3]
    )


def _validate_required_edges(value: object) -> TileEdgeRequirementV1 | None:
    if value is None:
        return None
    if type(value) is not str or value not in ("left_right", "top_bottom", "both"):
        raise TileEdgeQaConfigurationError(
            "required_edges must be 'left_right', 'top_bottom', 'both', or None"
        )
    return cast(TileEdgeRequirementV1, value)


def _validate_corner_requirement(value: object) -> bool:
    if type(value) is not bool:
        raise TileEdgeQaConfigurationError("require_equal_corners must be an exact bool")
    return value


def analyze_tile_edges(
    canvas: Canvas,
    *,
    required_edges: object = None,
    require_equal_corners: object = False,
) -> TileEdgeQaV1:
    """Return exact opposite-edge and corner equality facts for one tile raster.

    Equality is byte-exact over authoritative RGBA8 state, including RGB bytes stored
    below alpha zero. Opposite-edge facts are always reported. Contract satisfaction is
    emitted only when the caller explicitly requires an opposite-edge relation and/or
    equal corners.

    Only boundary pixels are visited: runtime is O(width + height), auxiliary analysis
    state is O(1), and no owned raster snapshot or per-pixel object graph is created.
    """

    if not isinstance(canvas, Canvas):
        raise TypeError("canvas must be a tracepixel.raster.Canvas")

    edge_requirement = _validate_required_edges(required_edges)
    corner_requirement = _validate_corner_requirement(require_equal_corners)

    width = canvas.width
    height = canvas.height
    rgba = canvas._rgba_view()

    left_right_mismatches = 0
    if width > 1:
        for y in range(height):
            row = y * width
            if not _pixel_equal(rgba, row, row + width - 1):
                left_right_mismatches += 1

    top_bottom_mismatches = 0
    if height > 1:
        bottom_row = (height - 1) * width
        for x in range(width):
            if not _pixel_equal(rgba, x, bottom_row + x):
                top_bottom_mismatches += 1

    top_left = 0
    top_right = width - 1
    bottom_left = (height - 1) * width
    bottom_right = bottom_left + width - 1
    corner_colors = {
        _packed_rgba(rgba, top_left),
        _packed_rgba(rgba, top_right),
        _packed_rgba(rgba, bottom_left),
        _packed_rgba(rgba, bottom_right),
    }
    corners_all_equal = len(corner_colors) == 1

    left_right_matches = left_right_mismatches == 0
    top_bottom_matches = top_bottom_mismatches == 0

    contract: TileEdgeContractCheckV1 | None = None
    if edge_requirement is not None or corner_requirement:
        edges_satisfied = (
            True
            if edge_requirement is None
            else left_right_matches
            if edge_requirement == "left_right"
            else top_bottom_matches
            if edge_requirement == "top_bottom"
            else left_right_matches and top_bottom_matches
        )
        contract = {
            "required_edges": edge_requirement,
            "require_equal_corners": corner_requirement,
            "satisfied": edges_satisfied and (not corner_requirement or corners_all_equal),
        }

    return {
        "schema": TILE_EDGE_QA_SCHEMA_V1,
        "left_right": {
            "compared_positions": height,
            "mismatched_positions": left_right_mismatches,
            "matches": left_right_matches,
        },
        "top_bottom": {
            "compared_positions": width,
            "mismatched_positions": top_bottom_mismatches,
            "matches": top_bottom_matches,
        },
        "corners": {
            "all_equal": corners_all_equal,
            "distinct_rgba_colors": len(corner_colors),
        },
        "contract": contract,
    }
