from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence, cast

from evidence.p6_v0.checkpoint import build_reference_bundle
from evidence.p6_v1.checkpoint import build_reference_sheet
from evidence.p6_v2.checkpoint import build_reference_composition
from tracepixel.preview import (
    StaticHtmlGallery,
    build_static_html_gallery,
    write_static_html_gallery,
)


def build_reference_gallery() -> StaticHtmlGallery:
    bundle = build_reference_bundle()
    sheet = build_reference_sheet()
    composition = build_reference_composition()

    first = build_static_html_gallery(bundle, sheet, composition)
    second = build_static_html_gallery(bundle, sheet, composition)
    if first != second:
        raise AssertionError("P6-V3 gallery is not deterministic across identical inputs")

    gallery_record = cast(dict[str, object], first.manifest["gallery"])
    if gallery_record["standalone"] is not True:
        raise AssertionError("P6-V3 gallery must be one standalone HTML review view")
    if gallery_record["external_dependencies"] != 0 or gallery_record["scripts"] != 0:
        raise AssertionError("P6-V3 baseline must require no external dependency or script")

    sources = cast(dict[str, object], first.manifest["sources"])
    preview_source = cast(dict[str, object], sources["preview_png"])
    preview_record = cast(dict[str, object], bundle.manifest["preview_png"])
    if preview_source["sha256"] != preview_record["sha256"]:
        raise AssertionError("P6-V3 final preview digest drifted from the P6-V0 bundle")

    stage_source = cast(dict[str, object], sources["stage_contact_sheet"])
    stage_record = cast(dict[str, object], sheet.manifest["sheet"])
    if stage_source["sha256"] != stage_record["sha256"]:
        raise AssertionError("P6-V3 stage sheet digest drifted from the P6-V1 composition")
    if stage_source["frame_count"] != len(cast(list[object], sheet.manifest["frames"])):
        raise AssertionError("P6-V3 stage frame count drifted from the P6-V1 manifest")
    if stage_source["linkage"] != "separate-reference":
        raise AssertionError("frozen P5-A5 bundle must explicitly disclose that it has no stage artifacts")

    metrics_source = cast(dict[str, object], sources["qa_metrics"])
    metrics_record = cast(dict[str, object], composition.manifest["composition"])
    if metrics_source["sha256"] != metrics_record["sha256"]:
        raise AssertionError("P6-V3 QA/metrics digest drifted from the P6-V2 composition")
    if metrics_source["qa_status"] != "pass" or metrics_source["finding_count"] != 0:
        raise AssertionError("frozen P5-A5 reference must remain deterministically QA-clean")

    authority = cast(dict[str, object], first.manifest["authority"])
    if authority["raster_truth"] != "unchanged":
        raise AssertionError("P6-V3 must not create a second raster authority")
    if authority["deterministic_qa"] != "source-evidence":
        raise AssertionError("P6-V3 presentation must not become deterministic QA authority")
    if authority["gallery"] != "presentation-only":
        raise AssertionError("P6-V3 HTML must remain presentation-only")
    if authority["perceptual"] != "not-included":
        raise AssertionError("P6-V3 must not silently cross unresolved G4")

    document = first.html.decode("utf-8")
    if "<script" in document.lower() or "http://" in document or "https://" in document:
        raise AssertionError("P6-V3 baseline must not load script or network resources")
    if 'name="viewport"' not in document or "Content-Security-Policy" not in document:
        raise AssertionError("P6-V3 baseline must carry mobile viewport and self-contained CSP metadata")
    return first


def _materialize_and_verify(gallery: StaticHtmlGallery, output: Path) -> None:
    write_static_html_gallery(gallery, output)
    if (output / "index.html").read_bytes() != gallery.html:
        raise AssertionError("materialized P6-V3 HTML differs from the in-memory gallery")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest != gallery.manifest:
        raise AssertionError("materialized P6-V3 manifest differs from the in-memory contract")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild the deterministic P6-V3 static HTML gallery from committed/provider-free evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional empty/non-existent directory to keep the rebuilt gallery",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    gallery = build_reference_gallery()
    if args.output is None:
        with TemporaryDirectory(prefix="tracepixel-p6-v3-") as temporary:
            _materialize_and_verify(gallery, Path(temporary) / "gallery")
    else:
        _materialize_and_verify(gallery, args.output)

    sources = cast(dict[str, object], gallery.manifest["sources"])
    stage_source = cast(dict[str, object], sources["stage_contact_sheet"])
    metrics_source = cast(dict[str, object], sources["qa_metrics"])
    print(
        "P6-V3 static HTML gallery checkpoint passed: "
        f"qa={metrics_source['qa_status']} stages={stage_source['frame_count']} "
        f"html_bytes={len(gallery.html)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
