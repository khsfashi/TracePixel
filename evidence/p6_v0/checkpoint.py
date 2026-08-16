from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence, cast

from tracepixel.agent import (
    AgentComplexityTelemetryV1,
    validate_agent_provider_proposal,
)
from tracepixel.model import ART_INTENT_SCHEMA_V1, ArtIntentV1, execute_pixel_program
from tracepixel.preview import PreviewBundle, build_preview_bundle, write_preview_bundle
from tracepixel.qa import (
    QA_POLICY_SCHEMA_V1,
    QaFindingsV1,
    analyze_color,
    analyze_connectivity,
    analyze_shape_outline,
    analyze_structural,
    evaluate_qa_policy,
)

ROOT = Path(__file__).resolve().parents[2]
P5_REFERENCE = ROOT / "evidence" / "p5_a5" / "reference-run"

_ART_INTENT = cast(
    ArtIntentV1,
    {
        "schema": ART_INTENT_SCHEMA_V1,
        "asset_class": "health-potion-icon",
        "canvas": {"width": 16, "height": 16},
        "composition": {
            "occupied_bounds": {"x": 3, "y": 2, "width": 10, "height": 13},
            "facing": "front",
            "symmetry": {"axis": "vertical", "strength": "required"},
            "light_direction": "top_left",
            "palette_budget": 6,
        },
    },
)

_QA_POLICY = {
    "schema": QA_POLICY_SCHEMA_V1,
    "rules": [
        {"rule": "structural.non_empty", "severity": "error"},
        {"rule": "structural.no_translucency", "severity": "error"},
        {"rule": "structural.no_edge_contact", "severity": "error"},
        {"rule": "color.maximum_colors", "severity": "error"},
        {"rule": "color.transparent_rgb_policy", "severity": "error"},
        {"rule": "connectivity.single_component", "severity": "error"},
        {"rule": "connectivity.no_isolated_pixels", "severity": "error"},
        {"rule": "shape.required_symmetry", "severity": "error"},
    ],
}


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _qa(canvas) -> QaFindingsV1:
    return evaluate_qa_policy(
        _QA_POLICY,
        structural=analyze_structural(canvas),
        color=analyze_color(
            canvas,
            max_colors=6,
            transparent_rgb_policy="require_zero",
        ),
        connectivity=analyze_connectivity(canvas),
        shape_outline=analyze_shape_outline(canvas, required_symmetry="vertical"),
    )


def build_reference_bundle() -> PreviewBundle:
    source_manifest = cast(dict[str, object], _json(P5_REFERENCE / "manifest.json"))
    calls = cast(list[dict[str, object]], _json(P5_REFERENCE / "provider-calls.json"))
    telemetry = cast(
        AgentComplexityTelemetryV1,
        _json(P5_REFERENCE / "telemetry.json"),
    )

    if len(calls) != 1:
        raise AssertionError("P6-V0 reference expects exactly one frozen P5-A5 provider call")
    proposal = validate_agent_provider_proposal(calls[0]["proposal"])
    if proposal["kind"] != "pixel_program":
        raise AssertionError("P6-V0 reference expects the frozen P5-A5 PixelProgram proposal")

    canvas = execute_pixel_program(proposal["payload"])
    findings = _qa(canvas)
    if findings["findings"]:
        raise AssertionError(f"frozen P5-A5 raster no longer passes deterministic QA: {findings!r}")

    bundle = build_preview_bundle(
        canvas,
        art_intent=_ART_INTENT,
        deterministic_qa=findings,
        complexity_evidence=telemetry,
        preview_scale=8,
    )

    authoritative_digest = hashlib.sha256(canvas.rgba_bytes()).hexdigest()
    if authoritative_digest != source_manifest["authoritative_rgba_sha256"]:
        raise AssertionError("P5-A5 authoritative RGBA digest drifted during provider-free replay")
    if bundle.file_bytes("image/native.png") != (P5_REFERENCE / "final.png").read_bytes():
        raise AssertionError("P6-V0 native PNG does not match frozen P5-A5 evidence")
    if bundle.file_bytes("image/preview-8x.png") != (P5_REFERENCE / "preview-8x.png").read_bytes():
        raise AssertionError("P6-V0 nearest preview does not match frozen P5-A5 evidence")
    if bundle.manifest["stage_artifacts"] != []:
        raise AssertionError("P5-A5 has no staged evidence; V0 must represent that explicitly")
    if bundle.manifest["complexity_evidence"] is None:
        raise AssertionError("P5-A5 Agent complexity evidence must be included when available")
    authority = cast(dict[str, object], bundle.manifest["authority"])
    if authority["perceptual"] != "not-included":
        raise AssertionError("P6-V0 must not silently cross the unresolved G4 perceptual gate")
    return bundle


def _materialize_and_verify(bundle: PreviewBundle, output: Path) -> None:
    write_preview_bundle(bundle, output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if manifest != bundle.manifest:
        raise AssertionError("materialized P6-V0 manifest differs from the in-memory contract")
    for item in bundle.files:
        if (output / item.path).read_bytes() != item.data:
            raise AssertionError(f"materialized P6-V0 file drifted: {item.path}")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild the deterministic P6-V0 preview bundle from frozen P5-A5 evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional empty/non-existent directory to keep the rebuilt bundle",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    bundle = build_reference_bundle()
    if args.output is None:
        with TemporaryDirectory(prefix="tracepixel-p6-v0-") as temporary:
            _materialize_and_verify(bundle, Path(temporary) / "bundle")
    else:
        _materialize_and_verify(bundle, args.output)

    source = cast(dict[str, object], bundle.manifest["source"])
    print(
        "P6-V0 preview bundle checkpoint passed: "
        f"files={len(bundle.files)} rgba={source['authoritative_rgba_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
