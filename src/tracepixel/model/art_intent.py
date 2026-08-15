from __future__ import annotations

from typing import Literal, TypedDict

ART_INTENT_SCHEMA_V1 = "tracepixel.art-intent.v1"

FacingV1 = Literal["left", "right", "up", "down", "front", "back"]
LightDirectionV1 = Literal[
    "top",
    "top_right",
    "right",
    "bottom_right",
    "bottom",
    "bottom_left",
    "left",
    "top_left",
]
SymmetryAxisV1 = Literal["vertical", "horizontal", "both"]
SymmetryStrengthV1 = Literal["hint", "required"]


class ArtIntentCanvasV1(TypedDict):
    """Canvas declaration shared with the P1 raster authority."""

    width: int
    height: int


class OccupiedBoundsV1(TypedDict):
    """Intended occupied rectangle in top-left, half-open canvas coordinates."""

    x: int
    y: int
    width: int
    height: int


class SymmetryIntentV1(TypedDict):
    """Explicit symmetry intent without claiming perceptual correctness."""

    axis: SymmetryAxisV1
    strength: SymmetryStrengthV1


class CompositionIntentV1(TypedDict):
    """Bounded composition metadata consumed by later P3 stages."""

    occupied_bounds: OccupiedBoundsV1 | None
    facing: FacingV1 | None
    symmetry: SymmetryIntentV1 | None
    light_direction: LightDirectionV1 | None
    palette_budget: int | None


class ArtIntentV1(TypedDict):
    """Versioned provider-neutral art-intent envelope for P3 staged authoring."""

    schema: Literal["tracepixel.art-intent.v1"]
    asset_class: str
    canvas: ArtIntentCanvasV1
    composition: CompositionIntentV1
