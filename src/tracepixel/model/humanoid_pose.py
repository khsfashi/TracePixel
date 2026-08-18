from __future__ import annotations

from typing import Literal, TypedDict

from .humanoid_profile import ConstraintModeV1, HumanoidProfileRefV1, HumanoidSideV1

HUMANOID_POSE_SCHEMA_V1 = "tracepixel.humanoid-pose.v1"
MAX_HUMANOID_POSE_RELATIONS_V1 = 64
MAX_HUMANOID_EQUIPMENT_ATTACHMENTS_V1 = 16

HumanoidPoseFacingV1 = Literal[
    "left",
    "right",
    "front",
    "rear",
    "three-quarter-left",
    "three-quarter-right",
]
HumanoidPoseRelationKindV1 = Literal[
    "landmark-relation",
    "articulation",
    "support-contact",
    "balance-contact",
    "silhouette-facing",
]
HumanoidPoseRangeUnitV1 = Literal["ratio", "degrees", "pixels"]
HumanoidEquipmentOccupancyIntentV1 = Literal["occupied", "clear"]
HumanoidEquipmentOcclusionIntentV1 = Literal["in-front", "behind", "mixed", "none"]


class HumanoidPoseRangeV1(TypedDict):
    minimum: float
    maximum: float
    unit: HumanoidPoseRangeUnitV1


class HumanoidPoseOrientationIntentV1(TypedDict):
    facing: HumanoidPoseFacingV1
    description: str


class HumanoidPoseRelationV1(TypedDict):
    relation_id: str
    kind: HumanoidPoseRelationKindV1
    mode: ConstraintModeV1
    landmark_ids: list[str]
    value_range: HumanoidPoseRangeV1 | None
    text: str


class HumanoidEquipmentAttachmentV1(TypedDict):
    attachment_id: str
    anchor_id: str
    equipment_id: str | None
    attachment_class: str
    side_intent: HumanoidSideV1
    occupancy_intent: HumanoidEquipmentOccupancyIntentV1
    overlap_occlusion_intent: HumanoidEquipmentOcclusionIntentV1
    text: str


class HumanoidPoseV1(TypedDict):
    """Provider-neutral static pose/equipment intent bound to one exact humanoid profile."""

    schema: Literal["tracepixel.humanoid-pose.v1"]
    pose_id: str
    pose_name: str
    profile_ref: HumanoidProfileRefV1
    orientation_intent: HumanoidPoseOrientationIntentV1
    relations: list[HumanoidPoseRelationV1]
    equipment_attachments: list[HumanoidEquipmentAttachmentV1]


class HumanoidPoseRefV1(TypedDict):
    pose_id: str
    pose_schema: Literal["tracepixel.humanoid-pose.v1"]
    sha256: str
