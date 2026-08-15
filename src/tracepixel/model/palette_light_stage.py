from __future__ import annotations

from typing import Literal, TypedDict

from .pixel_ir import PixelProgramV1

PALETTE_LIGHT_STAGE_SCHEMA_V1 = "tracepixel.palette-light-stage.v1"
PALETTE_LIGHT_STAGE_ID_V1 = "palette_light_ramp"
MAX_PALETTE_COLORS_V1 = 256
MAX_LIGHT_RAMPS_V1 = 32


class PaletteColorV1(TypedDict):
    """One authored palette role mapped to an exact RGBA8 color."""

    role: str
    rgba: list[int]


class LightRampV1(TypedDict):
    """Ordered authored light relationship between palette roles."""

    id: str
    colors: list[str]


class PaletteLightStageV1(TypedDict):
    """Provider-neutral P3-S3 palette/light-ramp contract."""

    schema: Literal["tracepixel.palette-light-stage.v1"]
    stage: Literal["palette_light_ramp"]
    palette: list[PaletteColorV1]
    ramps: list[LightRampV1]
    program: PixelProgramV1
