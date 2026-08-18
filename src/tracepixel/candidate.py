from __future__ import annotations

from dataclasses import dataclass

from tracepixel.raster import Canvas


class CandidateContractError(ValueError):
    """Raised when a generator-neutral candidate violates the intake contract."""


class CandidateProvenanceError(CandidateContractError):
    """Raised when candidate provenance is missing its required identity."""


def _validate_identity(label: str, value: object) -> str:
    if type(value) is not str or not value.strip():
        raise CandidateProvenanceError(f"candidate {label} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class CandidateProvenance:
    """Non-canonical source identity retained beside authoritative raster state."""

    backend: str
    candidate_id: str

    def __post_init__(self) -> None:
        _validate_identity("backend", self.backend)
        _validate_identity("candidate_id", self.candidate_id)


@dataclass(frozen=True, slots=True)
class RasterCandidate:
    """Generator-neutral candidate after its pixels have entered Canvas authority.

    The source backend and candidate identifier remain provenance only. ``canvas`` is
    the single authoritative mutable raster used by downstream QA/repair, while
    ``intake_rgba_sha256`` permanently identifies the exact pixels at intake time.
    """

    canvas: Canvas
    provenance: CandidateProvenance
    intake_rgba_sha256: str

    @classmethod
    def from_rgba8(
        cls,
        width: object,
        height: object,
        rgba8: object,
        provenance: CandidateProvenance,
    ) -> RasterCandidate:
        """Copy one external/RAW raster into authoritative Canvas storage exactly once."""
        if not isinstance(provenance, CandidateProvenance):
            raise CandidateContractError("candidate provenance must be CandidateProvenance")

        canvas = Canvas.from_rgba_bytes(width, height, rgba8)
        return cls(
            canvas=canvas,
            provenance=provenance,
            intake_rgba_sha256=canvas.rgba_sha256(),
        )

    @classmethod
    def from_canvas(
        cls,
        canvas: Canvas,
        provenance: CandidateProvenance,
    ) -> RasterCandidate:
        """Wrap an already-authoritative TracePixel Canvas without copying its pixels."""
        if not isinstance(canvas, Canvas):
            raise CandidateContractError("candidate canvas must be a Canvas")
        if not isinstance(provenance, CandidateProvenance):
            raise CandidateContractError("candidate provenance must be CandidateProvenance")

        return cls(
            canvas=canvas,
            provenance=provenance,
            intake_rgba_sha256=canvas.rgba_sha256(),
        )


__all__ = [
    "CandidateContractError",
    "CandidateProvenance",
    "CandidateProvenanceError",
    "RasterCandidate",
]
