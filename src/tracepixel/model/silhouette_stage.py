from __future__ import annotations

from typing import Literal, TypedDict

from .pixel_ir import PixelProgramV1

SILHOUETTE_STAGE_SCHEMA_V1 = "tracepixel.silhouette-stage.v1"
SILHOUETTE_STAGE_ID_V1 = "silhouette"


class SilhouetteStageV1(TypedDict):
    """Provider-neutral P3-S1 stage-local program for the primary occupied shape."""

    schema: Literal["tracepixel.silhouette-stage.v1"]
    stage: Literal["silhouette"]
    program: PixelProgramV1
