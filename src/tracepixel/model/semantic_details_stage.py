from __future__ import annotations

from typing import Literal, TypedDict

from .pixel_ir import PixelProgramV1

SEMANTIC_DETAILS_STAGE_SCHEMA_V1 = "tracepixel.semantic-details-stage.v1"
SEMANTIC_DETAILS_STAGE_ID_V1 = "semantic_details"
MAX_SEMANTIC_DETAILS_V1 = 64
MAX_PIXELS_PER_SEMANTIC_DETAIL_V1 = 64


class SemanticDetailV1(TypedDict):
    """One authored semantic locator mapped positionally to one bounded raw pixel patch."""

    id: str


class SemanticDetailsStageV1(TypedDict):
    """Provider-neutral P3-S5 semantic-detail contract."""

    schema: Literal["tracepixel.semantic-details-stage.v1"]
    stage: Literal["semantic_details"]
    details: list[SemanticDetailV1]
    program: PixelProgramV1
