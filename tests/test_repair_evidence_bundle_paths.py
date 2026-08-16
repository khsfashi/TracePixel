from __future__ import annotations

import unittest
from typing import cast

from tracepixel.repair import RepairEvidenceBundle, RepairEvidenceFile, RepairEvidenceV1


_PATH_KEYS = (
    "before_native_png",
    "before_preview_png",
    "after_native_png",
    "after_preview_png",
    "qa_evidence",
    "gallery_html",
)
_PATHS = (
    "before/native.png",
    "before/preview-8x.png",
    "after/native.png",
    "after/preview-8x.png",
    "evidence/qa-findings.json",
    "index.html",
)


def _path_manifest() -> RepairEvidenceV1:
    manifest: dict[str, object] = {}
    for key, path in zip(_PATH_KEYS, _PATHS, strict=True):
        manifest[key] = {"path": path}
    return cast(RepairEvidenceV1, manifest)


def _closed_files() -> tuple[RepairEvidenceFile, ...]:
    return (
        RepairEvidenceFile("manifest.json", b"manifest"),
        *(RepairEvidenceFile(path, b"artifact") for path in _PATHS),
    )


class RepairEvidenceBundlePathTests(unittest.TestCase):
    def test_duplicate_materialization_path_is_rejected_before_writer_can_overwrite(self) -> None:
        files = (*_closed_files(), RepairEvidenceFile("before/native.png", b"forged"))
        with self.assertRaisesRegex(ValueError, "must be unique"):
            RepairEvidenceBundle(manifest=_path_manifest(), files=files)

    def test_undeclared_materialization_path_is_rejected(self) -> None:
        files = (*_closed_files(), RepairEvidenceFile("unexpected.bin", b"unexpected"))
        with self.assertRaisesRegex(ValueError, "exactly match"):
            RepairEvidenceBundle(manifest=_path_manifest(), files=files)


if __name__ == "__main__":
    unittest.main()
