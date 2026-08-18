from __future__ import annotations

import hashlib
import unittest

from tracepixel.candidate import (
    CandidateContractError,
    CandidateProvenance,
    CandidateProvenanceError,
    RasterCandidate,
)
from tracepixel.raster import Canvas, RasterByteDataError


class CandidateTests(unittest.TestCase):
    def test_external_rgba8_is_copied_once_into_canvas_authority(self) -> None:
        source = bytearray((1, 2, 3, 4, 5, 6, 7, 8))
        candidate = RasterCandidate.from_rgba8(
            2,
            1,
            source,
            CandidateProvenance(backend="raw", candidate_id="run-1"),
        )

        source[0] = 99

        self.assertEqual(candidate.canvas.rgba_bytes(), bytes((1, 2, 3, 4, 5, 6, 7, 8)))
        self.assertEqual(
            candidate.intake_rgba_sha256,
            hashlib.sha256(bytes((1, 2, 3, 4, 5, 6, 7, 8))).hexdigest(),
        )

    def test_backend_identity_is_provenance_not_raster_truth(self) -> None:
        rgba = bytes((9, 8, 7, 6, 5, 4, 3, 2))
        raw = RasterCandidate.from_rgba8(
            2,
            1,
            rgba,
            CandidateProvenance(backend="raw", candidate_id="raw-1"),
        )
        external = RasterCandidate.from_rgba8(
            2,
            1,
            rgba,
            CandidateProvenance(backend="external", candidate_id="ext-1"),
        )

        self.assertNotEqual(raw.provenance, external.provenance)
        self.assertEqual(raw.canvas.rgba_bytes(), external.canvas.rgba_bytes())
        self.assertEqual(raw.intake_rgba_sha256, external.intake_rgba_sha256)

    def test_tracepixel_direct_can_wrap_existing_canvas_without_copy(self) -> None:
        canvas = Canvas.from_rgba_bytes(1, 1, bytes((10, 20, 30, 40)))
        candidate = RasterCandidate.from_canvas(
            canvas,
            CandidateProvenance(backend="tracepixel-direct", candidate_id="direct-1"),
        )

        self.assertIs(candidate.canvas, canvas)
        self.assertEqual(candidate.intake_rgba_sha256, canvas.rgba_sha256())

    def test_intake_digest_remains_bound_to_original_candidate_after_repair(self) -> None:
        candidate = RasterCandidate.from_rgba8(
            1,
            1,
            bytes((10, 20, 30, 40)),
            CandidateProvenance(backend="raw", candidate_id="raw-2"),
        )
        original_digest = candidate.intake_rgba_sha256

        candidate.canvas.set_pixel(0, 0, (40, 30, 20, 10))

        self.assertEqual(candidate.intake_rgba_sha256, original_digest)
        self.assertNotEqual(candidate.canvas.rgba_sha256(), original_digest)

    def test_malformed_byte_count_is_rejected_before_candidate_exists(self) -> None:
        with self.assertRaises(RasterByteDataError):
            RasterCandidate.from_rgba8(
                2,
                1,
                bytes((1, 2, 3, 4)),
                CandidateProvenance(backend="raw", candidate_id="bad-1"),
            )

    def test_non_byte_raster_input_is_rejected(self) -> None:
        with self.assertRaises(RasterByteDataError):
            RasterCandidate.from_rgba8(
                1,
                1,
                [1, 2, 3, 4],
                CandidateProvenance(backend="raw", candidate_id="bad-2"),
            )

    def test_provenance_requires_backend_and_candidate_identity(self) -> None:
        with self.assertRaises(CandidateProvenanceError):
            CandidateProvenance(backend="", candidate_id="candidate")
        with self.assertRaises(CandidateProvenanceError):
            CandidateProvenance(backend="raw", candidate_id="   ")

    def test_candidate_requires_typed_provenance(self) -> None:
        with self.assertRaises(CandidateContractError):
            RasterCandidate.from_rgba8(1, 1, bytes((1, 2, 3, 4)), "raw")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
