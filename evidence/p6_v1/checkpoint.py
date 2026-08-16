from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence, cast

from evidence.p3_s7.fixture import PREVIEW_SCALE, build_evidence
from tracepixel.model import STAGE_SEQUENCE_V1
from tracepixel.preview import (
    PreviewStageArtifact,
    StageContactSheet,
    build_stage_contact_sheet,
    write_stage_contact_sheet,
)


def build_reference_sheet() -> StageContactSheet:
    result, _ = build_evidence()
    artifacts = tuple(
        PreviewStageArtifact(
            stage=snapshot.stage,
            kind="stage-image",
            name=f"{index:02d}-{snapshot.stage.replace('_', '-')}@{PREVIEW_SCALE}x.png",
            media_type="image/png",
            data=snapshot.png,
        )
        for index, snapshot in enumerate(result.previews, start=1)
    )

    first = build_stage_contact_sheet(artifacts, columns=3)
    second = build_stage_contact_sheet(artifacts, columns=3)
    if first != second:
        raise AssertionError("P6-V1 contact sheet is not deterministic across identical inputs")

    frames = cast(list[dict[str, object]], first.manifest["frames"])
    expected_stages = list(STAGE_SEQUENCE_V1)
    if [frame["stage"] for frame in frames] != expected_stages:
        raise AssertionError("P6-V1 contact sheet does not preserve fixed P3 stage order")
    if len(frames) != len(result.previews):
        raise AssertionError("P6-V1 contact sheet did not include every authored P3 stage")

    for frame, snapshot in zip(frames, result.previews, strict=True):
        if frame["source_sha256"] != snapshot.metadata.png_sha256:
            raise AssertionError(f"stage PNG bytes drifted for {snapshot.stage}")
        if frame["source_width"] != snapshot.metadata.width:
            raise AssertionError(f"stage PNG width drifted for {snapshot.stage}")
        if frame["source_height"] != snapshot.metadata.height:
            raise AssertionError(f"stage PNG height drifted for {snapshot.stage}")

    layout = cast(dict[str, object], first.manifest["layout"])
    if layout["source_image_scaling"] != "none":
        raise AssertionError("P6-V1 must embed stage PNGs at their natural dimensions")

    authority = cast(dict[str, object], first.manifest["authority"])
    if authority["source_images"] != "embedded-byte-for-byte":
        raise AssertionError("P6-V1 must preserve exact stage PNG bytes")
    if authority["raster_truth"] != "unchanged":
        raise AssertionError("P6-V1 must not introduce a second raster authority")
    if authority["perceptual"] != "not-included":
        raise AssertionError("P6-V1 must not silently cross unresolved G4")

    return first


def _materialize_and_verify(sheet: StageContactSheet, output: Path) -> None:
    write_stage_contact_sheet(sheet, output)
    if (output / "stage-contact-sheet.svg").read_bytes() != sheet.svg:
        raise AssertionError("materialized P6-V1 SVG differs from in-memory contact sheet")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest != sheet.manifest:
        raise AssertionError("materialized P6-V1 manifest differs from in-memory contract")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild the deterministic P6-V1 contact sheet from committed P3 stage evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional empty/non-existent directory to keep the rebuilt contact sheet",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    sheet = build_reference_sheet()
    if args.output is None:
        with TemporaryDirectory(prefix="tracepixel-p6-v1-") as temporary:
            _materialize_and_verify(sheet, Path(temporary) / "sheet")
    else:
        _materialize_and_verify(sheet, args.output)

    layout = cast(dict[str, object], sheet.manifest["layout"])
    print(
        "P6-V1 stage contact sheet checkpoint passed: "
        f"frames={len(cast(list[object], sheet.manifest['frames']))} "
        f"layout={layout['columns']}x{layout['rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
