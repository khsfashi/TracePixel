from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tracepixel.preview.batch_review import (
    BATCH_REVIEW_PACKAGE_SCHEMA_V1,
    BatchReviewMember,
    BatchReviewPackageContractError,
    BatchReviewTilePlacement,
    build_batch_review_package,
    validate_batch_review_package,
    write_batch_review_package,
)
from tracepixel.raster import Canvas, export_native_png


def _png(width: int, height: int, color: tuple[int, int, int, int]) -> bytes:
    canvas = Canvas(width, height)
    canvas.set_pixels(
        [
            (x, y, color)
            for y in range(height)
            for x in range(width)
        ]
    )
    return export_native_png(canvas).png


class BatchReviewPackageTests(unittest.TestCase):
    def _member(
        self,
        member_id: str,
        *,
        asset_class: str = "item-icon",
        width: int = 2,
        height: int = 2,
        source_kind: str = "retained-output",
    ) -> BatchReviewMember:
        return BatchReviewMember(
            member_id=member_id,
            asset_class=asset_class,
            width=width,
            height=height,
            png=_png(width, height, (80, 120, 160, 255)),
            source_kind=source_kind,
            source_ref=f"results/{member_id}/final.png",
        )

    def test_builds_bilingual_network_free_package(self) -> None:
        package = build_batch_review_package((self._member("a"), self._member("b")))
        validate_batch_review_package(package)

        self.assertEqual(package.manifest["schema"], BATCH_REVIEW_PACKAGE_SCHEMA_V1)
        self.assertEqual(package.manifest["review_scope"], "retained-output")
        self.assertIn(b'<html lang="en">', package.html_en)
        self.assertIn('<html lang="ko">'.encode(), package.html_ko)
        self.assertNotIn(b"<script", package.html_en.lower())
        self.assertNotIn(b"https://", package.html_en.lower())

    def test_mixed_or_fixture_sources_fail_closed_to_fixture_scope(self) -> None:
        package = build_batch_review_package(
            (
                self._member("retained"),
                self._member("fixture", source_kind="presentation-fixture"),
            )
        )
        self.assertEqual(package.manifest["review_scope"], "presentation-fixture")
        self.assertIn(b'data-source-kind="presentation-fixture"', package.html_en)

    def test_rejects_png_dimension_mismatch(self) -> None:
        member = BatchReviewMember(
            member_id="bad",
            asset_class="item-icon",
            width=3,
            height=2,
            png=_png(2, 2, (1, 2, 3, 255)),
            source_kind="retained-output",
            source_ref="results/bad/final.png",
        )
        with self.assertRaisesRegex(BatchReviewPackageContractError, "png_dimension_mismatch"):
            build_batch_review_package((member,))

    def test_tile_layout_requires_dense_equal_size_terrain_grid(self) -> None:
        members = (
            self._member("t0", asset_class="terrain-tile"),
            self._member("t1", asset_class="terrain-tile"),
            self._member("t2", asset_class="terrain-tile"),
            self._member("t3", asset_class="terrain-tile"),
        )
        package = build_batch_review_package(
            members,
            tile_layout=(
                BatchReviewTilePlacement("t0", 0, 0),
                BatchReviewTilePlacement("t1", 1, 0),
                BatchReviewTilePlacement("t2", 0, 1),
                BatchReviewTilePlacement("t3", 1, 1),
            ),
        )
        self.assertEqual(
            package.manifest["tile_layout"],
            {
                "columns": 2,
                "rows": 2,
                "placements": [
                    {"member_id": "t0", "x": 0, "y": 0},
                    {"member_id": "t1", "x": 1, "y": 0},
                    {"member_id": "t2", "x": 0, "y": 1},
                    {"member_id": "t3", "x": 1, "y": 1},
                ],
            },
        )

        with self.assertRaisesRegex(BatchReviewPackageContractError, "sparse_tile_layout"):
            build_batch_review_package(
                members[:3],
                tile_layout=(
                    BatchReviewTilePlacement("t0", 0, 0),
                    BatchReviewTilePlacement("t1", 1, 0),
                    BatchReviewTilePlacement("t2", 1, 1),
                ),
            )

    def test_original_png_data_uri_is_embedded_once_per_language_page(self) -> None:
        member = self._member("one")
        package = build_batch_review_package((member,))
        marker = b"data:image/png;base64,"
        self.assertEqual(package.html_en.count(marker), 1)
        self.assertEqual(package.html_ko.count(marker), 1)

    def test_write_requires_empty_directory(self) -> None:
        package = build_batch_review_package((self._member("a"),))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "review"
            write_batch_review_package(package, output)
            self.assertTrue((output / "index.html").is_file())
            self.assertTrue((output / "index.ko.html").is_file())
            self.assertTrue((output / "manifest.json").is_file())

            with self.assertRaisesRegex(BatchReviewPackageContractError, "nonempty_output"):
                write_batch_review_package(package, output)


if __name__ == "__main__":
    unittest.main()
