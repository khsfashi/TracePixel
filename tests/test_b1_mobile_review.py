from __future__ import annotations

import json
from pathlib import Path

from evidence.b1_s0.mobile_review import build_package


def test_b1_mobile_review_builds_28_blind_entries(tmp_path: Path) -> None:
    package = build_package(tmp_path, source_sha="a" * 40)

    assert package["entry_count"] == 28
    assert package["method_labels_exposed"] is False
    assert package["offline"] is True

    ko = (tmp_path / "index.html").read_text(encoding="utf-8")
    en = (tmp_path / "index.en.html").read_text(encoding="utf-8")
    metadata = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))

    for method_id in ("tracepixel-post-p7-v1", "raw-pixel-program-v1"):
        assert method_id not in ko
        assert method_id not in en
        assert method_id not in json.dumps(metadata)

    assert "TracePixel B1 블라인드 모바일 평가" in ko
    assert "TracePixel B1 blind mobile review" in en
    assert ko.count('class="card" data-review-id=') == 28
    assert en.count('class="card" data-review-id=') == 28
    assert "B1-T3-02" in ko
    assert "다음 미평가" in ko
    assert "tracepixel.b1-owner-review.v1" in ko
