from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from evidence.b0_s0.mobile_review import MOBILE_REVIEW_SCHEMA_V1, build_mobile_package
from evidence.b0_s0.review import OWNER_REVIEW_SCHEMA_V1


class B0S0MobileReviewTests(unittest.TestCase):
    def test_mobile_package_is_korean_first_blind_and_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "package"
            manifest = build_mobile_package(out, source_sha="1" * 40)
            self.assertEqual(manifest["schema"], MOBILE_REVIEW_SCHEMA_V1)
            self.assertEqual(manifest["default_language"], "ko")
            self.assertEqual(manifest["entry_count"], 28)
            self.assertIs(manifest["method_labels_exposed"], False)
            self.assertEqual(manifest["output_contract"], OWNER_REVIEW_SCHEMA_V1)
            self.assertEqual(manifest["provider_calls"], 0)
            self.assertEqual(manifest["vlm_calls"], 0)
            self.assertEqual(set(path.name for path in out.iterdir()), {"index.ko.html", "index.html", "manifest.json"})

            ko = (out / "index.ko.html").read_bytes()
            en = (out / "index.html").read_bytes()
            for page in (ko, en):
                self.assertNotIn(b"tracepixel-staged-v1", page)
                self.assertNotIn(b"raw-pixel-program-v1", page)
                self.assertIn(b"data:image/png;base64,", page)
                self.assertIn(OWNER_REVIEW_SCHEMA_V1.encode(), page)
                self.assertNotIn(b"https://", page)
                self.assertNotIn(b"http://", page)
            self.assertIn("인식 가능성".encode("utf-8"), ko)
            self.assertIn("원본 1배 크기 가독성".encode("utf-8"), ko)
            self.assertIn("스타일 일관성".encode("utf-8"), ko)
            self.assertIn("평가 JSON 저장".encode("utf-8"), ko)
            self.assertIn(b'lang="ko"', ko)

            disk_manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(disk_manifest, manifest)

    def test_source_sha_is_pinned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                build_mobile_package(Path(temp) / "package", source_sha="main")


if __name__ == "__main__":
    unittest.main()
