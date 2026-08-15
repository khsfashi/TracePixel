from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, TypedDict, cast

from tracepixel.raster import Canvas
from tracepixel.raster.contract import ColorValueError, validate_rgba8

COLOR_QA_SCHEMA_V1 = "tracepixel.color-qa.v1"
MAX_COLOR_POLICY_COLORS_V1 = 256

TransparentRgbPolicyV1 = Literal["allow", "require_zero"]


class ColorQaConfigurationError(ValueError):
    """Raised when an explicit P4-Q1 palette/color policy input is invalid."""


class ColorCountFactsV1(TypedDict):
    visible_rgba_colors: int


class TransparentRgbFactsV1(TypedDict):
    nonzero_rgb_pixels: int
    has_nonzero_rgb: bool


class PaletteMembershipCheckV1(TypedDict):
    palette_size: int
    visible_pixels: int
    matching_visible_pixels: int
    nonmatching_visible_pixels: int
    nonmatching_visible_colors: int
    satisfied: bool


class MaximumColorCheckV1(TypedDict):
    limit: int
    actual_visible_colors: int
    satisfied: bool


class TransparentRgbCheckV1(TypedDict):
    policy: TransparentRgbPolicyV1
    nonzero_rgb_pixels: int
    satisfied: bool


class ColorQaV1(TypedDict):
    schema: Literal["tracepixel.color-qa.v1"]
    colors: ColorCountFactsV1
    transparent_rgb: TransparentRgbFactsV1
    palette_membership: PaletteMembershipCheckV1 | None
    maximum_colors: MaximumColorCheckV1 | None
    transparent_rgb_policy: TransparentRgbCheckV1 | None


def _pack_rgba(red: int, green: int, blue: int, alpha: int) -> int:
    return (red << 24) | (green << 16) | (blue << 8) | alpha


def _validate_palette(palette: object) -> frozenset[int] | None:
    if palette is None:
        return None
    if not isinstance(palette, Sequence) or isinstance(palette, (str, bytes, bytearray)):
        raise ColorQaConfigurationError("palette must be an ordered sequence of RGBA8 colors or None")
    if len(palette) > MAX_COLOR_POLICY_COLORS_V1:
        raise ColorQaConfigurationError(
            f"palette must contain at most {MAX_COLOR_POLICY_COLORS_V1} colors"
        )

    packed_colors: set[int] = set()
    for index, color in enumerate(palette):
        try:
            validate_rgba8(color)
        except ColorValueError as exc:
            raise ColorQaConfigurationError(f"palette[{index}]: {exc}") from exc
        assert isinstance(color, Sequence)
        packed = _pack_rgba(color[0], color[1], color[2], color[3])
        if packed in packed_colors:
            raise ColorQaConfigurationError(f"palette[{index}] duplicates an earlier RGBA8 color")
        packed_colors.add(packed)
    return frozenset(packed_colors)


def _validate_max_colors(max_colors: object) -> int | None:
    if max_colors is None:
        return None
    if type(max_colors) is not int or not 1 <= max_colors <= MAX_COLOR_POLICY_COLORS_V1:
        raise ColorQaConfigurationError(
            f"max_colors must be an exact integer in [1, {MAX_COLOR_POLICY_COLORS_V1}] or None"
        )
    return max_colors


def _validate_transparent_rgb_policy(policy: object) -> TransparentRgbPolicyV1 | None:
    if policy is None:
        return None
    if policy not in ("allow", "require_zero") or type(policy) is not str:
        raise ColorQaConfigurationError(
            "transparent_rgb_policy must be 'allow', 'require_zero', or None"
        )
    return cast(TransparentRgbPolicyV1, policy)


def analyze_color(
    canvas: Canvas,
    *,
    palette: object = None,
    max_colors: object = None,
    transparent_rgb_policy: object = None,
) -> ColorQaV1:
    """Return exact P4-Q1 color facts plus only explicitly requested policy checks.

    Palette membership and maximum-color checks apply to structurally visible pixels
    (stored alpha != 0). RGB bytes hidden under alpha zero are kept out of the visible
    palette count and are reported independently through transparent-RGB facts/policy.

    The scan borrows Canvas' package-internal read-only RGBA view. It keeps packed integer
    color sets rather than per-pixel objects or coordinate graphs.
    """

    if not isinstance(canvas, Canvas):
        raise TypeError("canvas must be a tracepixel.raster.Canvas")

    palette_set = _validate_palette(palette)
    maximum = _validate_max_colors(max_colors)
    transparent_policy = _validate_transparent_rgb_policy(transparent_rgb_policy)

    rgba = canvas._rgba_view()
    visible_colors: set[int] = set()
    nonmatching_colors: set[int] | None = set() if palette_set is not None else None

    visible_pixels = 0
    matching_visible_pixels = 0
    nonmatching_visible_pixels = 0
    transparent_nonzero_rgb_pixels = 0

    for offset in range(0, len(rgba), 4):
        red = rgba[offset]
        green = rgba[offset + 1]
        blue = rgba[offset + 2]
        alpha = rgba[offset + 3]

        if alpha == 0:
            if red != 0 or green != 0 or blue != 0:
                transparent_nonzero_rgb_pixels += 1
            continue

        visible_pixels += 1
        packed = _pack_rgba(red, green, blue, alpha)
        visible_colors.add(packed)

        if palette_set is not None:
            if packed in palette_set:
                matching_visible_pixels += 1
            else:
                nonmatching_visible_pixels += 1
                assert nonmatching_colors is not None
                nonmatching_colors.add(packed)

    visible_color_count = len(visible_colors)

    palette_check: PaletteMembershipCheckV1 | None = None
    if palette_set is not None:
        assert nonmatching_colors is not None
        palette_check = {
            "palette_size": len(palette_set),
            "visible_pixels": visible_pixels,
            "matching_visible_pixels": matching_visible_pixels,
            "nonmatching_visible_pixels": nonmatching_visible_pixels,
            "nonmatching_visible_colors": len(nonmatching_colors),
            "satisfied": nonmatching_visible_pixels == 0,
        }

    maximum_check: MaximumColorCheckV1 | None = None
    if maximum is not None:
        maximum_check = {
            "limit": maximum,
            "actual_visible_colors": visible_color_count,
            "satisfied": visible_color_count <= maximum,
        }

    transparent_check: TransparentRgbCheckV1 | None = None
    if transparent_policy is not None:
        transparent_check = {
            "policy": transparent_policy,
            "nonzero_rgb_pixels": transparent_nonzero_rgb_pixels,
            "satisfied": (
                True
                if transparent_policy == "allow"
                else transparent_nonzero_rgb_pixels == 0
            ),
        }

    result: ColorQaV1 = {
        "schema": COLOR_QA_SCHEMA_V1,
        "colors": {"visible_rgba_colors": visible_color_count},
        "transparent_rgb": {
            "nonzero_rgb_pixels": transparent_nonzero_rgb_pixels,
            "has_nonzero_rgb": transparent_nonzero_rgb_pixels > 0,
        },
        "palette_membership": palette_check,
        "maximum_colors": maximum_check,
        "transparent_rgb_policy": transparent_check,
    }
    return result
