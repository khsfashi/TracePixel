from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evidence.p6_v0.checkpoint import build_reference_bundle
from evidence.p6_v1.checkpoint import build_reference_sheet
from evidence.p6_v2.checkpoint import build_reference_composition
from tracepixel.preview import (
    STATIC_HTML_GALLERY_SCHEMA_V1,
    QaMetricsComposition,
    StaticHtmlGalleryContractError,
    build_static_html_gallery,
    write_static_html_gallery,
)


class StaticHtmlGalleryTests(unittest.TestCase):
    def test_reference_gallery_is_repeatable_self_contained_and_keeps_authority_separate(self) -> None:
        bundle = build_reference_bundle()
        sheet = build_reference_sheet()
        composition = build_reference_composition()

        first = build_static_html_gallery(bundle, sheet, composition)
        second = build_static_html_gallery(bundle, sheet, composition)

        self.assertEqual(first, second)
        self.assertEqual(first.manifest["schema"], STATIC_HTML_GALLERY_SCHEMA_V1)
        gallery_record = first.manifest["gallery"]
        self.assertTrue(gallery_record["standalone"])  # type: ignore[index]
        self.assertEqual(gallery_record["external_dependencies"], 0)  # type: ignore[index]
        self.assertEqual(gallery_record["scripts"], 0)  # type: ignore[index]
        self.assertEqual(
            gallery_record["sha256"],  # type: ignore[index]
            hashlib.sha256(first.html).hexdigest(),
        )

        sources = first.manifest["sources"]
        self.assertEqual(sources["qa_metrics"]["qa_status"], "pass")  # type: ignore[index]
        self.assertEqual(sources["qa_metrics"]["finding_count"], 0)  # type: ignore[index]
        self.assertEqual(sources["stage_contact_sheet"]["frame_count"], 6)  # type: ignore[index]
        self.assertEqual(
            sources["stage_contact_sheet"]["linkage"],  # type: ignore[index]
            "separate-reference",
        )

        authority = first.manifest["authority"]
        self.assertEqual(authority["raster_truth"], "unchanged")  # type: ignore[index]
        self.assertEqual(authority["deterministic_qa"], "source-evidence")  # type: ignore[index]
        self.assertEqual(authority["gallery"], "presentation-only")  # type: ignore[index]
        self.assertEqual(authority["perceptual"], "not-included")  # type: ignore[index]
        self.assertEqual(authority["human_judgment"], "not-recorded")  # type: ignore[index]

        document = first.html.decode("utf-8")
        preview = bundle.file_bytes("image/preview-8x.png")
        self.assertIn(
            "data:image/png;base64," + base64.b64encode(preview).decode("ascii"),
            document,
        )
        self.assertEqual(document.count("data:image/svg+xml;base64,"), 2)
        self.assertIn('name="viewport"', document)
        self.assertIn("Content-Security-Policy", document)
        self.assertNotIn("<script", document.lower())
        self.assertNotIn("http://", document)
        self.assertNotIn("https://", document)

    def test_tampered_composition_bytes_are_rejected(self) -> None:
        bundle = build_reference_bundle()
        sheet = build_reference_sheet()
        composition = build_reference_composition()
        tampered = QaMetricsComposition(
            manifest=composition.manifest,
            svg=composition.svg + b"\n",
        )

        with self.assertRaises(StaticHtmlGalleryContractError) as context:
            build_static_html_gallery(bundle, sheet, tampered)
        self.assertEqual(context.exception.code, "source_size_mismatch")

    def test_writer_materializes_exact_html_and_manifest_and_refuses_stale_output(self) -> None:
        gallery = build_static_html_gallery(
            build_reference_bundle(),
            build_reference_sheet(),
            build_reference_composition(),
        )

        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "gallery"
            write_static_html_gallery(gallery, output)
            self.assertEqual((output / "index.html").read_bytes(), gallery.html)
            self.assertEqual(
                json.loads((output / "manifest.json").read_text(encoding="utf-8")),
                gallery.manifest,
            )

            with self.assertRaises(StaticHtmlGalleryContractError) as context:
                write_static_html_gallery(gallery, output)
            self.assertEqual(context.exception.code, "output_not_empty")


if __name__ == "__main__":
    unittest.main()
