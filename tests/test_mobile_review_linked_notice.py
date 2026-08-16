from __future__ import annotations

from typing import cast
import unittest

from evidence.p3_s7.fixture import PREVIEW_SCALE, art_intent, build_evidence
from tracepixel.preview import (
    PreviewStageArtifact,
    build_mobile_review_package,
    build_preview_bundle,
    build_qa_metrics_composition,
    build_stage_contact_sheet,
    build_static_html_gallery,
)
from tracepixel.qa import QA_FINDINGS_SCHEMA_V1, QaFindingsV1


class MobileReviewLinkedNoticeTests(unittest.TestCase):
    def test_linked_stage_bundle_gets_positive_exact_provenance_notice(self) -> None:
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
        gallery = build_static_html_gallery(
            bundle,
            build_stage_contact_sheet(artifacts, columns=3),
            build_qa_metrics_composition(bundle),
        )
        package = build_mobile_review_package(gallery)

        self.assertEqual(package.manifest["stage_linkage"], "bundle-stage-artifacts")
        self.assertIn(b'data-stage-linkage="bundle-stage-artifacts"', package.html_en)
        self.assertIn(b"Linked stages", package.html_en)
        self.assertIn("연결된 단계".encode(), package.html_ko)
        self.assertNotIn(b"not provenance of this final output", package.html_en)


if __name__ == "__main__":
    unittest.main()
