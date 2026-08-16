from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

from .execution import RepairExecutionV1

REPAIR_EVIDENCE_SCHEMA_V1 = "tracepixel.repair-evidence.v1"

RepairEvidenceMediaTypeV1 = Literal["image/png", "application/json", "text/html"]


class RepairEvidenceArtifactV1(TypedDict):
    """One byte-addressed F4 review artifact bound to optional authoritative RGBA identity."""

    path: str
    media_type: RepairEvidenceMediaTypeV1
    size_bytes: int
    sha256: str
    authoritative_rgba_sha256: str | None


class RepairEvidenceAuthorityV1(TypedDict):
    raster: Literal["authoritative-rgba-derived"]
    deterministic_qa: Literal["deterministic"]
    human: Literal["not-recorded"]
    perceptual: Literal["not-included"]


class RepairEvidenceV1(TypedDict):
    """P7-F4 before/after visual evidence retaining the exact F3 execution provenance."""

    schema: Literal["tracepixel.repair-evidence.v1"]
    execution: RepairExecutionV1
    preview_scale: int
    before_native_png: RepairEvidenceArtifactV1
    before_preview_png: RepairEvidenceArtifactV1
    after_native_png: RepairEvidenceArtifactV1
    after_preview_png: RepairEvidenceArtifactV1
    qa_evidence: RepairEvidenceArtifactV1
    gallery_html: RepairEvidenceArtifactV1
    authority: RepairEvidenceAuthorityV1


@dataclass(frozen=True, slots=True)
class RepairEvidenceFile:
    path: str
    data: bytes


@dataclass(frozen=True, slots=True)
class RepairEvidenceBundle:
    manifest: RepairEvidenceV1
    files: tuple[RepairEvidenceFile, ...]

    def file_bytes(self, path: str) -> bytes:
        for item in self.files:
            if item.path == path:
                return item.data
        raise KeyError(path)
