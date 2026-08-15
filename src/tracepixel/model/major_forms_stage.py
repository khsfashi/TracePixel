from __future__ import annotations

from typing import Literal, TypedDict

from .pixel_ir import PixelProgramV1

MAJOR_FORMS_STAGE_SCHEMA_V1 = "tracepixel.major-forms-stage.v1"
MAJOR_FORMS_STAGE_ID_V1 = "major_forms"
MAX_MAJOR_FORMS_V1 = 16


class MajorFormV1(TypedDict):
    """Stable domain-neutral identity for one P3-S2 major form."""

    id: str


class MajorFormsStageV1(TypedDict):
    """Provider-neutral P3-S2 form identities mapped to PixelProgram operations."""

    schema: Literal["tracepixel.major-forms-stage.v1"]
    stage: Literal["major_forms"]
    forms: list[MajorFormV1]
    program: PixelProgramV1
