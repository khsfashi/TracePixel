from __future__ import annotations

import json
from pathlib import Path

from tracepixel.model import (
    ART_INTENT_SCHEMA_V1,
    MAJOR_FORMS_STAGE_ID_V1,
    MAJOR_FORMS_STAGE_SCHEMA_V1,
    OUTLINE_CLEANUP_STAGE_ID_V1,
    OUTLINE_CLEANUP_STAGE_SCHEMA_V1,
    PALETTE_LIGHT_STAGE_ID_V1,
    PALETTE_LIGHT_STAGE_SCHEMA_V1,
    PIXEL_PROGRAM_SCHEMA_V1,
    SEMANTIC_DETAILS_STAGE_ID_V1,
    SEMANTIC_DETAILS_STAGE_SCHEMA_V1,
    SHADING_STAGE_ID_V1,
    SHADING_STAGE_SCHEMA_V1,
    SILHOUETTE_STAGE_ID_V1,
    SILHOUETTE_STAGE_SCHEMA_V1,
    STAGE_PLAN_SCHEMA_V1,
    ArtIntentV1,
    StagePipelineResult,
    StagePlanV1,
    execute_stage_pipeline,
)

EVIDENCE_SCHEMA = "tracepixel.p3-s7-fixture-evidence.v1"
FIXTURE_ID = "p3-s7-potion-staged-v1"
PREVIEW_SCALE = 2


def art_intent() -> ArtIntentV1:
    return {
        "schema": ART_INTENT_SCHEMA_V1,
        "asset_class": "potion",
        "canvas": {"width": 16, "height": 16},
        "composition": {
            "occupied_bounds": {"x": 4, "y": 2, "width": 8, "height": 10},
            "facing": None,
            "symmetry": {"axis": "vertical", "strength": "hint"},
            "light_direction": "top_left",
            "palette_budget": 7,
        },
    }


def _program(*operations: dict[str, object]) -> dict[str, object]:
    return {
        "schema": PIXEL_PROGRAM_SCHEMA_V1,
        "canvas": {"width": 16, "height": 16},
        "operations": list(operations),
    }


def _set_pixels(pixels: list[list[int]]) -> dict[str, object]:
    return {"op": "set_pixels", "pixels": pixels}


def stage_plan() -> StagePlanV1:
    silhouette_pixels: list[list[int]] = []
    rows = {
        3: range(7, 9),
        4: range(6, 10),
        5: range(6, 10),
        6: range(5, 11),
        7: range(4, 12),
        8: range(4, 12),
        9: range(4, 12),
        10: range(5, 11),
        11: range(6, 10),
    }
    for y, xs in rows.items():
        silhouette_pixels.extend([[x, y, 88, 96, 120, 255] for x in xs])

    liquid_block = [
        [x, y, 120, 80, 120, 255]
        for y in range(8, 11)
        for x in range(5, 11)
    ]
    liquid_final = [
        [x, y, 220, 88, 64, 255]
        for y in range(8, 11)
        for x in range(5, 11)
    ]

    silhouette = {
        "schema": SILHOUETTE_STAGE_SCHEMA_V1,
        "stage": SILHOUETTE_STAGE_ID_V1,
        "program": _program(_set_pixels(silhouette_pixels)),
    }
    major_forms = {
        "schema": MAJOR_FORMS_STAGE_SCHEMA_V1,
        "stage": MAJOR_FORMS_STAGE_ID_V1,
        "forms": [{"id": "cork"}, {"id": "liquid_block"}],
        "program": _program(
            _set_pixels(
                [
                    [7, 2, 180, 120, 64, 255],
                    [8, 2, 180, 120, 64, 255],
                    [7, 3, 180, 120, 64, 255],
                    [8, 3, 180, 120, 64, 255],
                ]
            ),
            _set_pixels(liquid_block),
        ),
    }
    palette_light = {
        "schema": PALETTE_LIGHT_STAGE_SCHEMA_V1,
        "stage": PALETTE_LIGHT_STAGE_ID_V1,
        "palette": [
            {"role": "transparent", "rgba": [0, 0, 0, 0]},
            {"role": "outline_dark", "rgba": [32, 36, 48, 255]},
            {"role": "body_shadow", "rgba": [44, 48, 64, 255]},
            {"role": "body_base", "rgba": [88, 96, 120, 255]},
            {"role": "body_highlight", "rgba": [152, 160, 184, 255]},
            {"role": "cork", "rgba": [180, 120, 64, 255]},
            {"role": "liquid", "rgba": [220, 88, 64, 255]},
        ],
        "ramps": [
            {"id": "body", "colors": ["body_shadow", "body_base", "body_highlight"]}
        ],
        "program": _program(_set_pixels(liquid_final)),
    }
    shading = {
        "schema": SHADING_STAGE_SCHEMA_V1,
        "stage": SHADING_STAGE_ID_V1,
        "applications": [
            {
                "id": "body_light",
                "ramp_id": "body",
                "source_role": "body_base",
                "target_role": "body_highlight",
                "relation": "toward_light",
            },
            {
                "id": "body_shadow",
                "ramp_id": "body",
                "source_role": "body_base",
                "target_role": "body_shadow",
                "relation": "away_from_light",
            },
        ],
        "program": _program(
            _set_pixels(
                [
                    [5, 6, 152, 160, 184, 255],
                    [5, 7, 152, 160, 184, 255],
                ]
            ),
            _set_pixels(
                [
                    [10, 9, 44, 48, 64, 255],
                    [10, 10, 44, 48, 64, 255],
                ]
            ),
        ),
    }
    semantic_details = {
        "schema": SEMANTIC_DETAILS_STAGE_SCHEMA_V1,
        "stage": SEMANTIC_DETAILS_STAGE_ID_V1,
        "details": [{"id": "liquid_glint"}],
        "program": _program(
            _set_pixels(
                [
                    [6, 8, 152, 160, 184, 255],
                    [6, 9, 152, 160, 184, 255],
                ]
            )
        ),
    }
    outline_cleanup = {
        "schema": OUTLINE_CLEANUP_STAGE_SCHEMA_V1,
        "stage": OUTLINE_CLEANUP_STAGE_ID_V1,
        "actions": [
            {"id": "left_edge", "kind": "outline"},
            {"id": "right_cutout", "kind": "cleanup"},
        ],
        "program": _program(
            _set_pixels(
                [
                    [4, 7, 32, 36, 48, 255],
                    [4, 8, 32, 36, 48, 255],
                ]
            ),
            _set_pixels([[11, 8, 0, 0, 0, 0]]),
        ),
    }

    return {
        "schema": STAGE_PLAN_SCHEMA_V1,
        "stages": [
            {
                "stage": SILHOUETTE_STAGE_ID_V1,
                "document": silhouette,
                "skip_reason": None,
            },
            {
                "stage": MAJOR_FORMS_STAGE_ID_V1,
                "document": major_forms,
                "skip_reason": None,
            },
            {
                "stage": PALETTE_LIGHT_STAGE_ID_V1,
                "document": palette_light,
                "skip_reason": None,
            },
            {
                "stage": SHADING_STAGE_ID_V1,
                "document": shading,
                "skip_reason": None,
            },
            {
                "stage": SEMANTIC_DETAILS_STAGE_ID_V1,
                "document": semantic_details,
                "skip_reason": None,
            },
            {
                "stage": OUTLINE_CLEANUP_STAGE_ID_V1,
                "document": outline_cleanup,
                "skip_reason": None,
            },
        ],
    }


def build_evidence() -> tuple[StagePipelineResult, dict[str, object]]:
    result = execute_stage_pipeline(
        art_intent(),
        stage_plan(),
        preview_scale=PREVIEW_SCALE,
    )
    preview_files = [
        {
            "stage": snapshot.stage,
            "file": f"{index:02d}-{snapshot.stage.replace('_', '-')}@{PREVIEW_SCALE}x.png",
            "png_sha256": snapshot.metadata.png_sha256,
        }
        for index, snapshot in enumerate(result.previews, start=1)
    ]
    manifest = {
        "schema": EVIDENCE_SCHEMA,
        "fixture_id": FIXTURE_ID,
        "preview_scale": PREVIEW_SCALE,
        "pipeline": result.evidence,
        "outputs": {
            "authoritative_rgba": "final.rgba",
            "previews": preview_files,
        },
    }
    return result, manifest


def write_evidence(directory: Path) -> None:
    result, manifest = build_evidence()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "final.rgba").write_bytes(result.canvas.rgba_bytes())
    for index, snapshot in enumerate(result.previews, start=1):
        filename = f"{index:02d}-{snapshot.stage.replace('_', '-')}@{PREVIEW_SCALE}x.png"
        (directory / filename).write_bytes(snapshot.png)
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_evidence(Path(__file__).resolve().parent)
