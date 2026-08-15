from __future__ import annotations

from typing import Literal, TypedDict

from .pixel_ir import PixelProgramV1

OUTLINE_CLEANUP_STAGE_SCHEMA_V1 = "tracepixel.outline-cleanup-stage.v1"
OUTLINE_CLEANUP_STAGE_ID_V1 = "outline_cleanup"
MAX_OUTLINE_CLEANUP_ACTIONS_V1 = 64
MAX_PIXELS_PER_OUTLINE_CLEANUP_ACTION_V1 = 64

OutlineCleanupKindV1 = Literal["outline", "cleanup"]


class OutlineCleanupActionV1(TypedDict):
    """One authored outline/cleanup locator mapped to one bounded raw pixel patch."""

    id: str
    kind: OutlineCleanupKindV1


class OutlineCleanupStageV1(TypedDict):
    """Provider-neutral P3-S6 outline/cleanup contract."""

    schema: Literal["tracepixel.outline-cleanup-stage.v1"]
    stage: Literal["outline_cleanup"]
    actions: list[OutlineCleanupActionV1]
    program: PixelProgramV1
