from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evidence.p6_v0.checkpoint import build_reference_bundle
from tracepixel.preview import (
    QA_METRICS_COMPOSITION_SCHEMA_V1,
    QaMetricsCompositionContractError,
    build_qa_metrics_composition,
    write_qa_metrics_composition,
)


class QaMetricsCompositionTests(unittest.TestCase):
    def test_reference_composition_is_repeatable_and_keeps_authority_separate(self) -> None:
        bundle = build_reference_bundle()

        first = build_qa_metrics_composition(bundle)
        second = build_qa_metrics_composition(bundle)

        self.assertEqual(first, second)
        self.assertEqual(first.manifest["schema"], QA_METRICS_COMPOSITION_SCHEMA_V1)
        self.assertEqual(first.manifest["deterministic_qa"]["status"], "pass")  # type: ignore[index]
        self.assertEqual(first.manifest["deterministic_qa"]["finding_count"], 0)  # type: ignore[index]
        telemetry = first.manifest["agent_complexity"]["telemetry"]  # type: ignore[index]
        self.assertEqual(telemetry["tool_calls"], 1)  # type: ignore[index]
        self.assertEqual(telemetry["iterations"], 1)  # type: ignore[index]
        self.assertEqual(telemetry["changed_pixels"], 96)  # type: ignore[index]

        authority = first.manifest["authority"]
        self.assertEqual(authority["raster_truth"], "unchanged")  # type: ignore[index]
        self.assertEqual(authority["deterministic_qa"], "source-evidence")  # type: ignore[index]
        self.assertEqual(authority["complexity"], "observational")  # type: ignore[index]
        self.assertEqual(authority["perceptual"], "not-included")  # type: ignore[index]
        self.assertEqual(authority["human_judgment"], "not-included")  # type: ignore[index]

        preview = bundle.file_bytes("image/preview-8x.png")
        svg = first.svg.decode("utf-8")
        self.assertIn(base64.b64encode(preview).decode("ascii"), svg)
        self.assertEqual(
            first.manifest["composition"]["sha256"],  # type: ignore[index]
            hashlib.sha256(first.svg).hexdigest(),
        )
        self.assertEqual(first.manifest["image"]["source_image_scaling"], "none")  # type: ignore[index]

    def test_manifest_digest_mismatch_is_rejected(self) -> None:
        bundle = build_reference_bundle()
        preview_record = bundle.manifest["preview_png"]
        assert isinstance(preview_record, dict)
        preview_record["sha256"] = "0" * 64

        with self.assertRaises(QaMetricsCompositionContractError) as context:
            build_qa_metrics_composition(bundle)
        self.assertEqual(context.exception.code, "bundle_digest_mismatch")

    def test_writer_materializes_exact_svg_and_manifest_and_refuses_stale_output(self) -> None:
        composition = build_qa_metrics_composition(build_reference_bundle())

        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "composition"
            write_qa_metrics_composition(composition, output)
            self.assertEqual((output / "qa-metrics.svg").read_bytes(), composition.svg)
            self.assertEqual(
                json.loads((output / "manifest.json").read_text(encoding="utf-8")),
                composition.manifest,
            )

            with self.assertRaises(QaMetricsCompositionContractError) as context:
                write_qa_metrics_composition(composition, output)
            self.assertEqual(context.exception.code, "output_not_empty")


if __name__ == "__main__":
    unittest.main()
