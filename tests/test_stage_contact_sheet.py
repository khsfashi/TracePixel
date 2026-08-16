from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tracepixel.preview import (
    STAGE_CONTACT_SHEET_SCHEMA_V1,
    PreviewStageArtifact,
    StageContactSheetContractError,
    build_stage_contact_sheet,
    write_stage_contact_sheet,
)
from tracepixel.raster import Canvas, export_nearest_preview_png


def _stage_png(color: tuple[int, int, int, int]) -> bytes:
    canvas = Canvas(2, 2)
    canvas.set_pixel(0, 0, color)
    canvas.set_pixel(1, 1, color)
    return export_nearest_preview_png(canvas, scale=2).png


class StageContactSheetTests(unittest.TestCase):
    def test_sheet_is_repeatable_stage_ordered_and_embeds_exact_pngs(self) -> None:
        silhouette_png = _stage_png((255, 0, 0, 255))
        outline_png = _stage_png((0, 0, 255, 255))
        artifacts = (
            PreviewStageArtifact(
                stage="outline_cleanup",
                kind="stage-image",
                name="06-outline.png",
                media_type="image/png",
                data=outline_png,
            ),
            PreviewStageArtifact(
                stage="silhouette",
                kind="stage-image",
                name="01-silhouette.png",
                media_type="image/png",
                data=silhouette_png,
            ),
        )

        first = build_stage_contact_sheet(artifacts, columns=2)
        second = build_stage_contact_sheet(artifacts, columns=2)

        self.assertEqual(first, second)
        self.assertEqual(first.manifest["schema"], STAGE_CONTACT_SHEET_SCHEMA_V1)
        frames = first.manifest["frames"]
        self.assertEqual(
            [frame["stage"] for frame in frames],  # type: ignore[index]
            ["silhouette", "outline_cleanup"],
        )
        self.assertEqual(
            first.manifest["sheet"]["sha256"],  # type: ignore[index]
            hashlib.sha256(first.svg).hexdigest(),
        )
        layout = first.manifest["layout"]
        self.assertEqual(layout["columns"], 2)  # type: ignore[index]
        self.assertEqual(layout["rows"], 1)  # type: ignore[index]
        self.assertEqual(layout["source_image_scaling"], "none")  # type: ignore[index]
        authority = first.manifest["authority"]
        self.assertEqual(authority["source_images"], "embedded-byte-for-byte")  # type: ignore[index]
        self.assertEqual(authority["raster_truth"], "unchanged")  # type: ignore[index]
        self.assertEqual(authority["perceptual"], "not-included")  # type: ignore[index]

        svg = first.svg.decode("utf-8")
        self.assertIn(base64.b64encode(silhouette_png).decode("ascii"), svg)
        self.assertIn(base64.b64encode(outline_png).decode("ascii"), svg)
        self.assertIn(hashlib.sha256(silhouette_png).hexdigest(), svg)
        self.assertIn(hashlib.sha256(outline_png).hexdigest(), svg)

    def test_non_image_evidence_is_ignored_but_duplicate_stage_images_are_rejected(self) -> None:
        stage_png = _stage_png((0, 255, 0, 255))
        evidence = PreviewStageArtifact(
            stage="silhouette",
            kind="stage-evidence",
            name="transition.json",
            media_type="application/json",
            data=b'{"schema":"fixture.stage-evidence.v1"}',
        )
        image = PreviewStageArtifact(
            stage="silhouette",
            kind="stage-image",
            name="preview.png",
            media_type="image/png",
            data=stage_png,
        )

        sheet = build_stage_contact_sheet((evidence, image))
        self.assertEqual(len(sheet.manifest["frames"]), 1)  # type: ignore[arg-type]

        with self.assertRaises(StageContactSheetContractError) as context:
            build_stage_contact_sheet((image, image))
        self.assertEqual(context.exception.code, "duplicate_stage_image")

    def test_missing_or_malformed_stage_images_are_rejected(self) -> None:
        evidence_only = PreviewStageArtifact(
            stage="silhouette",
            kind="stage-evidence",
            name="transition.json",
            media_type="application/json",
            data=b"{}",
        )
        with self.assertRaises(StageContactSheetContractError) as context:
            build_stage_contact_sheet((evidence_only,))
        self.assertEqual(context.exception.code, "no_stage_images")

        malformed = PreviewStageArtifact(
            stage="silhouette",
            kind="stage-image",
            name="preview.png",
            media_type="image/png",
            data=b"\x89PNG\r\n\x1a\n",
        )
        with self.assertRaises(StageContactSheetContractError) as context:
            build_stage_contact_sheet((malformed,))
        self.assertEqual(context.exception.code, "invalid_stage_png")

    def test_writer_materializes_exact_svg_and_manifest_and_refuses_stale_output(self) -> None:
        image = PreviewStageArtifact(
            stage="silhouette",
            kind="stage-image",
            name="preview.png",
            media_type="image/png",
            data=_stage_png((255, 255, 0, 255)),
        )
        sheet = build_stage_contact_sheet((image,))

        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "sheet"
            write_stage_contact_sheet(sheet, output)
            self.assertEqual((output / "stage-contact-sheet.svg").read_bytes(), sheet.svg)
            self.assertEqual(
                json.loads((output / "manifest.json").read_text(encoding="utf-8")),
                sheet.manifest,
            )

            with self.assertRaises(StageContactSheetContractError) as context:
                write_stage_contact_sheet(sheet, output)
            self.assertEqual(context.exception.code, "output_not_empty")


if __name__ == "__main__":
    unittest.main()
