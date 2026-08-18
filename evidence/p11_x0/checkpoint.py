from __future__ import annotations

from tracepixel.candidate import CandidateProvenance, RasterCandidate
from tracepixel.raster import Canvas


def main() -> int:
    rgba = bytes(
        (
            0,
            0,
            0,
            0,
            24,
            32,
            40,
            255,
            88,
            96,
            104,
            255,
            0,
            0,
            0,
            0,
        )
    )

    raw = RasterCandidate.from_rgba8(
        2,
        2,
        rgba,
        CandidateProvenance(backend="raw", candidate_id="p11-x0-raw"),
    )
    external = RasterCandidate.from_rgba8(
        2,
        2,
        rgba,
        CandidateProvenance(backend="external", candidate_id="p11-x0-external"),
    )
    direct_canvas = Canvas.from_rgba_bytes(2, 2, rgba)
    direct = RasterCandidate.from_canvas(
        direct_canvas,
        CandidateProvenance(
            backend="tracepixel-direct",
            candidate_id="p11-x0-direct",
        ),
    )

    candidates = (raw, external, direct)
    expected_digest = raw.intake_rgba_sha256
    for candidate in candidates:
        if candidate.canvas.rgba_bytes() != rgba:
            raise SystemExit("P11-X0 checkpoint failed: candidate raster bytes diverged")
        if candidate.intake_rgba_sha256 != expected_digest:
            raise SystemExit("P11-X0 checkpoint failed: provenance changed raster identity")

    if direct.canvas is not direct_canvas:
        raise SystemExit("P11-X0 checkpoint failed: direct Canvas was copied")
    if len({candidate.provenance.backend for candidate in candidates}) != 3:
        raise SystemExit("P11-X0 checkpoint failed: backend provenance was not retained")

    original_digest = raw.intake_rgba_sha256
    raw.canvas.set_pixel(0, 0, (1, 2, 3, 4))
    if raw.intake_rgba_sha256 != original_digest:
        raise SystemExit("P11-X0 checkpoint failed: intake identity mutated after repair")
    if raw.canvas.rgba_sha256() == original_digest:
        raise SystemExit("P11-X0 checkpoint failed: current Canvas digest did not change")

    print("P11-X0 generator-neutral candidate intake checkpoint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
