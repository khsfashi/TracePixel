from __future__ import annotations

from copy import deepcopy
from typing import cast
import unittest

from evidence.p3_s7.fixture import PREVIEW_SCALE, art_intent, build_evidence
from tracepixel.preview import (
    PreviewStageArtifact,
    StageContactSheet,
    StaticHtmlGalleryContractError,
    build_preview_bundle,
    build_qa_metrics_composition,
    build_stage_contact_sheet,
    build_static_html_gallery,
)
from tracepixel.qa import QA_FINDINGS_SCHEMA_V1, QaFindingsV1


class StaticGalleryStageLinkageTests(unittest.TestCase):
    def _linked_inputs(self):
        result, _ = build_evidence()
        artifacts = tuple(
            PreviewStageArtifact(
                stage=snapshot.stage,
                kind="stage-image",
                name=f"{index:02d}-{snapshot.stage.replace('_', '-')}-{PREVIEW_SCALE}x.png",
                media_type="image/png",
                data=snapshot.png,
            )
            for index, snapshot in enumerate(result.previews, start=1)
        )
        findings = cast(
            QaFindingsV1,
            {"schema": QA_FINDINGS_SCHEMA_V1, "findings": []},
        )
        bundle = build_preview_bundle(
            result.canvas,
            art_intent=art_intent(),
            deterministic_qa=findings,
            stage_artifacts=artifacts,
            preview_scale=PREVIEW_SCALE,
        )
        sheet = build_stage_contact_sheet(artifacts, columns=3)
        composition = build_qa_metrics_composition(bundle)
        return bundle, sheet, composition

    def test_bundle_stage_artifacts_are_exactly_linked_by_path_and_digest(self) -> None:
        bundle, sheet, composition = self._linked_inputs()
        gallery = build_static_html_gallery(bundle, sheet, composition)
        stage_source = gallery.manifest["sources"]["stage_contact_sheet"]  # type: ignore[index]
        self.assertEqual(stage_source["linkage"], "bundle-stage-artifacts")

    def test_stage_digest_drift_is_rejected_instead_of_being_presented_as_provenance(self) -> None:
        bundle, sheet, composition = self._linked_inputs()
        manifest = deepcopy(sheet.manifest)
        frames = manifest["frames"]
        assert isinstance(frames, list)
        assert isinstance(frames[0], dict)
        frames[0]["source_sha256"] = "0" * 64
        tampered = StageContactSheet(manifest=manifest, svg=sheet.svg)

        with self.assertRaises(StaticHtmlGalleryContractError) as context:
            build_static_html_gallery(bundle, tampered, composition)
        self.assertEqual(context.exception.code, "stage_source_mismatch")


if __name__ == "__main__":
    unittest.main()
