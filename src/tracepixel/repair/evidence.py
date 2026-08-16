from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

from .execution import RepairExecutionV1

REPAIR_EVIDENCE_SCHEMA_V1 = "tracepixel.repair-evidence.v1"

RepairEvidenceMediaTypeV1 = Literal["image/png", "application/json", "text/html"]

_BUNDLE_ARTIFACT_KEYS = (
    "before_native_png",
    "before_preview_png",
    "after_native_png",
    "after_preview_png",
    "qa_evidence",
    "gallery_html",
)


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

    def __post_init__(self) -> None:
        """Keep one immutable, closed materialization path set per valid F4 manifest."""

        actual_paths = [item.path for item in self.files]
        if len(actual_paths) != len(set(actual_paths)):
            raise ValueError("repair evidence bundle file paths must be unique")

        # Malformed manifests are rejected by validate_repair_evidence(). When the path-bearing
        # shape is present, fail early here so a writer can never verify one file and then
        # overwrite it through a duplicate or undeclared later entry.
        try:
            expected_paths = {"manifest.json"}
            expected_paths.update(self.manifest[key]["path"] for key in _BUNDLE_ARTIFACT_KEYS)
        except (KeyError, TypeError):
            return
        if set(actual_paths) != expected_paths:
            raise ValueError("repair evidence bundle files must exactly match manifest artifact paths")

    def file_bytes(self, path: str) -> bytes:
        for item in self.files:
            if item.path == path:
                return item.data
        raise KeyError(path)
