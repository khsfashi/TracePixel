from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tracepixel.qa import (
    QA_POLICY_SCHEMA_V1,
    analyze_color,
    analyze_connectivity,
    analyze_shape_outline,
    analyze_structural,
    analyze_tile_edges,
    evaluate_qa_policy,
)
from tracepixel.raster import Canvas

EVIDENCE_SCHEMA = "tracepixel.p4-q5-seeded-evidence.v1"
CANVAS_SIZE = (5, 5)

POLICY = {
    "schema": QA_POLICY_SCHEMA_V1,
    "rules": [
        {"rule": "structural.non_empty", "severity": "error"},
        {"rule": "structural.no_translucency", "severity": "warning"},
        {"rule": "structural.no_edge_contact", "severity": "warning"},
        {"rule": "color.palette_membership", "severity": "error"},
        {"rule": "color.maximum_colors", "severity": "error"},
        {"rule": "color.transparent_rgb_policy", "severity": "error"},
        {"rule": "connectivity.single_component", "severity": "error"},
        {"rule": "connectivity.no_isolated_pixels", "severity": "warning"},
        {"rule": "shape.required_symmetry", "severity": "error"},
        {"rule": "tile.contract", "severity": "error"},
    ],
}

CLEAN_EDITS = (
    (2, 1, (20, 40, 200, 255)),
    (2, 2, (20, 40, 200, 255)),
    (2, 3, (20, 40, 200, 255)),
)

SEEDED_DEFECT_EDITS = (
    (0, 0, (200, 30, 30, 255)),
    (2, 1, (20, 40, 200, 255)),
    (2, 2, (20, 40, 200, 255)),
    (1, 2, (30, 200, 60, 128)),
    (4, 4, (9, 9, 9, 0)),
)


def _case(*, clean: bool) -> dict[str, Any]:
    canvas = Canvas(*CANVAS_SIZE)
    edits = CLEAN_EDITS if clean else SEEDED_DEFECT_EDITS
    canvas.set_pixels(edits)

    palette = [(20, 40, 200, 255)] if clean else [
        (200, 30, 30, 255),
        (20, 40, 200, 255),
    ]
    color = analyze_color(
        canvas,
        palette=palette,
        max_colors=1 if clean else 2,
        transparent_rgb_policy="require_zero",
    )
    structural = analyze_structural(canvas)
    connectivity = analyze_connectivity(canvas)
    shape_outline = analyze_shape_outline(canvas, required_symmetry="vertical")
    tile_edge = analyze_tile_edges(
        canvas,
        required_edges="both",
        require_equal_corners=True,
    )
    findings = evaluate_qa_policy(
        POLICY,
        structural=structural,
        color=color,
        connectivity=connectivity,
        shape_outline=shape_outline,
        tile_edge=tile_edge,
    )

    return {
        "edits": edits,
        "finding_count": len(findings["findings"]),
        "findings": findings,
    }


def build_evidence() -> dict[str, Any]:
    return {
        "schema": EVIDENCE_SCHEMA,
        "canvas": {"width": CANVAS_SIZE[0], "height": CANVAS_SIZE[1]},
        "policy": POLICY,
        "cases": {
            "clean": _case(clean=True),
            "seeded_defects": _case(clean=False),
        },
    }


def canonical_json(evidence: object) -> str:
    return json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def main() -> None:
    output = Path(__file__).with_name("structural.json")
    output.write_text(canonical_json(build_evidence()), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
