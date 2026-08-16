from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence, cast

from evidence.p6_v0.checkpoint import build_reference_bundle
from tracepixel.preview import (
    QaMetricsComposition,
    build_qa_metrics_composition,
    write_qa_metrics_composition,
)


def build_reference_composition() -> QaMetricsComposition:
    bundle = build_reference_bundle()
    first = build_qa_metrics_composition(bundle)
    second = build_qa_metrics_composition(bundle)
    if first != second:
        raise AssertionError("P6-V2 composition is not deterministic across identical inputs")

    image = cast(dict[str, object], first.manifest["image"])
    preview_record = cast(dict[str, object], bundle.manifest["preview_png"])
    if image["sha256"] != preview_record["sha256"]:
        raise AssertionError("P6-V2 preview PNG digest drifted from the P6-V0 bundle")
    if image["source_image_scaling"] != "none":
        raise AssertionError("P6-V2 must present the existing preview without implicit resampling")

    qa = cast(dict[str, object], first.manifest["deterministic_qa"])
    if qa["status"] != "pass" or qa["finding_count"] != 0:
        raise AssertionError("frozen P5-A5 reference must remain deterministically QA-clean")

    complexity = cast(dict[str, object], first.manifest["agent_complexity"])
    telemetry = cast(dict[str, object], complexity["telemetry"])
    expected = {
        "tool_calls": 1,
        "operation_calls": 1,
        "iterations": 1,
        "revisions": 1,
        "changed_pixels": 96,
        "visual_observation_calls": 0,
        "human_interventions": 0,
    }
    for field, value in expected.items():
        if telemetry[field] != value:
            raise AssertionError(f"P6-V2 complexity field drifted: {field}")

    composition = cast(dict[str, object], first.manifest["composition"])
    if composition.get("layout") != "vertical-stack-v1":
        raise AssertionError("P6-V2 reference must use the mobile-safe vertical stack")
    width = composition.get("width")
    content_width = composition.get("content_width")
    if type(width) is not int or width > 400:
        raise AssertionError("P6-V2 reference composition width must remain phone review friendly")
    if type(content_width) is not int or content_width != width - 32:
        raise AssertionError("P6-V2 content width must preserve the fixed 16px side padding")

    authority = cast(dict[str, object], first.manifest["authority"])
    if authority["deterministic_qa"] != "source-evidence":
        raise AssertionError("P6-V2 presentation must not become deterministic QA authority")
    if authority["complexity"] != "observational":
        raise AssertionError("P6-V2 must keep Agent complexity observational")
    if authority["perceptual"] != "not-included":
        raise AssertionError("P6-V2 must not silently cross unresolved G4")
    if authority["human_judgment"] != "not-included":
        raise AssertionError("P6-V2 must not encode human judgment as machine evidence")
    return first


def _materialize_and_verify(composition: QaMetricsComposition, output: Path) -> None:
    write_qa_metrics_composition(composition, output)
    if (output / "qa-metrics.svg").read_bytes() != composition.svg:
        raise AssertionError("materialized P6-V2 SVG differs from in-memory composition")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest != composition.manifest:
        raise AssertionError("materialized P6-V2 manifest differs from in-memory contract")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild the deterministic P6-V2 QA/metrics composition from frozen P5-A5 evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional empty/non-existent directory to keep the rebuilt composition",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    composition = build_reference_composition()
    if args.output is None:
        with TemporaryDirectory(prefix="tracepixel-p6-v2-") as temporary:
            _materialize_and_verify(composition, Path(temporary) / "composition")
    else:
        _materialize_and_verify(composition, args.output)

    qa = cast(dict[str, object], composition.manifest["deterministic_qa"])
    telemetry = cast(dict[str, object], cast(dict[str, object], composition.manifest["agent_complexity"])["telemetry"])
    layout = cast(dict[str, object], composition.manifest["composition"])
    print(
        "P6-V2 QA/metrics composition checkpoint passed: "
        f"qa={qa['status']} tool_calls={telemetry['tool_calls']} "
        f"changed_pixels={telemetry['changed_pixels']} layout={layout['layout']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
