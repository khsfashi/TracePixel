from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tracepixel.agent import AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1
from tracepixel.model import ART_INTENT_SCHEMA_V1
from tracepixel.preview import (
    PREVIEW_BUNDLE_SCHEMA_V1,
    PreviewBundleContractError,
    PreviewStageArtifact,
    build_preview_bundle,
    write_preview_bundle,
)
from tracepixel.qa import QA_FINDINGS_SCHEMA_V1
from tracepixel.raster import Canvas, export_native_png


def _intent(width: int, height: int) -> dict[str, object]:
    return {
        "schema": ART_INTENT_SCHEMA_V1,
        "asset_class": "preview-bundle-fixture",
        "canvas": {"width": width, "height": height},
        "composition": {
            "occupied_bounds": None,
            "facing": None,
            "symmetry": None,
            "light_direction": None,
            "palette_budget": None,
        },
    }


def _empty_findings() -> dict[str, object]:
    return {"schema": QA_FINDINGS_SCHEMA_V1, "findings": []}


def _complexity() -> dict[str, object]:
    return {
        "schema": AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1,
        "input_tokens": 10,
        "output_tokens": 4,
        "tool_calls": 1,
        "operation_calls": 1,
        "exposed_concept_count": 5,
        "visual_observation_calls": 0,
        "iterations": 1,
        "revisions": 1,
        "changed_pixels": 1,
        "wall_time_ns": 1,
        "api_cost_usd_micros": None,
        "human_interventions": 0,
        "failure_category": None,
    }


class PreviewBundleTests(unittest.TestCase):
    def _canvas(self) -> Canvas:
        canvas = Canvas(2, 2)
        canvas.set_pixels(
            [
                (0, 0, (255, 0, 0, 255)),
                (1, 0, (0, 255, 0, 255)),
                (0, 1, (0, 0, 255, 255)),
            ]
        )
        return canvas

    def test_core_bundle_is_repeatable_and_tied_to_authoritative_rgba(self) -> None:
        canvas = self._canvas()

        first = build_preview_bundle(
            canvas,
            art_intent=_intent(2, 2),  # type: ignore[arg-type]
            deterministic_qa=_empty_findings(),  # type: ignore[arg-type]
            preview_scale=3,
        )
        second = build_preview_bundle(
            canvas,
            art_intent=_intent(2, 2),  # type: ignore[arg-type]
            deterministic_qa=_empty_findings(),  # type: ignore[arg-type]
            preview_scale=3,
        )

        self.assertEqual(first.files, second.files)
        self.assertEqual(first.manifest, second.manifest)
        self.assertEqual(first.manifest["schema"], PREVIEW_BUNDLE_SCHEMA_V1)
        self.assertEqual(
            [item.path for item in first.files],
            [
                "manifest.json",
                "image/native.png",
                "image/preview-3x.png",
                "evidence/intent.json",
                "evidence/qa-findings.json",
            ],
        )
        source = first.manifest["source"]
        self.assertIsInstance(source, dict)
        self.assertEqual(
            source["authoritative_rgba_sha256"],  # type: ignore[index]
            hashlib.sha256(canvas.rgba_bytes()).hexdigest(),
        )
        authority = first.manifest["authority"]
        self.assertEqual(authority["perceptual"], "not-included")  # type: ignore[index]
        self.assertIsNone(first.manifest["complexity_evidence"])
        self.assertEqual(first.manifest["stage_artifacts"], [])
        self.assertEqual(json.loads(first.file_bytes("manifest.json")), first.manifest)

    def test_optional_complexity_and_stage_artifacts_are_hashed_and_stage_ordered(self) -> None:
        canvas = self._canvas()
        stage_png = export_native_png(canvas).png
        stage_evidence = b'{"schema":"fixture.stage-evidence.v1"}\n'

        bundle = build_preview_bundle(
            canvas,
            art_intent=_intent(2, 2),  # type: ignore[arg-type]
            deterministic_qa=_empty_findings(),  # type: ignore[arg-type]
            complexity_evidence=_complexity(),  # type: ignore[arg-type]
            stage_artifacts=(
                PreviewStageArtifact(
                    stage="outline_cleanup",
                    kind="stage-evidence",
                    name="transition.json",
                    media_type="application/json",
                    data=stage_evidence,
                ),
                PreviewStageArtifact(
                    stage="silhouette",
                    kind="stage-image",
                    name="preview.png",
                    media_type="image/png",
                    data=stage_png,
                ),
            ),
            preview_scale=2,
        )

        records = bundle.manifest["stage_artifacts"]
        self.assertEqual(
            [record["stage"] for record in records],  # type: ignore[index]
            ["silhouette", "outline_cleanup"],
        )
        self.assertEqual(
            [record["path"] for record in records],  # type: ignore[index]
            [
                "stages/silhouette/preview.png",
                "stages/outline_cleanup/transition.json",
            ],
        )
        self.assertEqual(
            records[0]["sha256"],  # type: ignore[index]
            hashlib.sha256(stage_png).hexdigest(),
        )
        self.assertEqual(
            records[1]["sha256"],  # type: ignore[index]
            hashlib.sha256(stage_evidence).hexdigest(),
        )
        self.assertIsNotNone(bundle.manifest["complexity_evidence"])
        self.assertEqual(
            json.loads(bundle.file_bytes("evidence/agent-complexity.json"))["tool_calls"],
            1,
        )

    def test_writer_materializes_complete_bundle_and_refuses_stale_output(self) -> None:
        canvas = self._canvas()
        bundle = build_preview_bundle(
            canvas,
            art_intent=_intent(2, 2),  # type: ignore[arg-type]
            deterministic_qa=_empty_findings(),  # type: ignore[arg-type]
            preview_scale=2,
        )

        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            write_preview_bundle(bundle, output)
            for item in bundle.files:
                self.assertEqual((output / item.path).read_bytes(), item.data)

            with self.assertRaises(PreviewBundleContractError) as context:
                write_preview_bundle(bundle, output)
            self.assertEqual(context.exception.code, "output_not_empty")


if __name__ == "__main__":
    unittest.main()
