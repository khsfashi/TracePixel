from __future__ import annotations

from typing import Literal, TypedDict

from .research_profile import ConstraintModeV1, MorphologyProfileRefV1, MorphologyValueRangeV1

CREATURE_POSE_SCHEMA_V1 = "tracepixel.creature-pose.v1"
MAX_POSE_RELATIONS_V1 = 64

PoseFacingV1 = Literal[
    "left",
    "right",
    "front",
    "rear",
    "three-quarter-left",
    "three-quarter-right",
]
PoseRelationKindV1 = Literal[
    "landmark-relation",
    "articulation",
    "support-contact",
    "silhouette-facing",
]


class PoseOrientationIntentV1(TypedDict):
    facing: PoseFacingV1
    description: str


class CreaturePoseRelationV1(TypedDict):
    relation_id: str
    kind: PoseRelationKindV1
    mode: ConstraintModeV1
    landmark_ids: list[str]
    value_range: MorphologyValueRangeV1 | None
    morphology_constraint_ids: list[str]
    text: str


class CreaturePoseV1(TypedDict):
    """Provider-neutral pose intent bound to one exact morphology profile; never raster or physics authority."""

    schema: Literal["tracepixel.creature-pose.v1"]
    pose_id: str
    pose_name: str
    morphology_ref: MorphologyProfileRefV1
    orientation_intent: PoseOrientationIntentV1
    relations: list[CreaturePoseRelationV1]


class CreaturePoseRefV1(TypedDict):
    pose_id: str
    pose_schema: Literal["tracepixel.creature-pose.v1"]
    sha256: str
