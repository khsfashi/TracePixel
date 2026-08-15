from __future__ import annotations

from typing import Literal, TypedDict

from .pixel_ir import PixelProgramV1

SHADING_STAGE_SCHEMA_V1 = "tracepixel.shading-stage.v1"
SHADING_STAGE_ID_V1 = "shading"
MAX_SHADING_APPLICATIONS_V1 = 64

ShadingRelationV1 = Literal["toward_light", "away_from_light"]


class ShadingApplicationV1(TypedDict):
    """One bounded light-ramp transition mapped positionally to one PixelProgram operation."""

    id: str
    ramp_id: str
    source_role: str
    target_role: str
    relation: ShadingRelationV1


class ShadingStageV1(TypedDict):
    """Provider-neutral P3-S4 shading contract."""

    schema: Literal["tracepixel.shading-stage.v1"]
    stage: Literal["shading"]
    applications: list[ShadingApplicationV1]
    program: PixelProgramV1
