from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from evidence.p6_v3.checkpoint import build_reference_gallery
from tracepixel.preview.mobile_review import (
    build_mobile_review_package,
    write_mobile_review_package,
)


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "trusted-gallery-artifact.yml"

_REQUIRED_TOKENS = (
    "push:\n    branches:\n      - main",
    "workflow_dispatch:",
    "permissions:\n  contents: read",
    "github.repository == 'khsfashi/TracePixel'",
    "github.ref == 'refs/heads/main'",
    "github.event_name == 'push'",
    "github.event_name == 'workflow_dispatch'",
    "runs-on: ubuntu-latest",
    "timeout-minutes: 10",
    "ref: ${{ github.sha }}",
    "persist-credentials: false",
    "python-version: '3.12'",
    "python -m evidence.p6_v5.checkpoint --output artifacts/p6-v4-static-gallery",
    "name: tracepixel-static-gallery-${{ github.sha }}",
    "path: artifacts/p6-v4-static-gallery",
    "if-no-files-found: error",
    "retention-days: 14",
)

_FORBIDDEN_TOKENS = (
    "pull_request",
    "self-hosted",
    "secrets.",
    "contents: write",
    "id-token: write",
    "attestations: write",
    "\n  schedule:",
)

_EXPECTED_ACTIONS = (
    "uses: actions/checkout@v4",
    "uses: actions/setup-python@v5",
    "uses: actions/upload-artifact@v4",
)


class ArtifactWorkflowPolicyError(AssertionError):
    """Raised when the P6-V4 publication workflow crosses its frozen trust boundary."""


def validate_workflow_policy(text: str) -> None:
    """Apply the intentionally small P6-V4 trust-boundary regression policy."""

    for token in _REQUIRED_TOKENS:
        if token not in text:
            raise ArtifactWorkflowPolicyError(f"required workflow policy token missing: {token!r}")

    for token in _FORBIDDEN_TOKENS:
        if token in text:
            raise ArtifactWorkflowPolicyError(f"forbidden workflow policy token present: {token!r}")

    actions = tuple(
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("uses:")
    )
    if actions != _EXPECTED_ACTIONS:
        raise ArtifactWorkflowPolicyError(
            f"workflow action surface drifted: expected {_EXPECTED_ACTIONS!r}, got {actions!r}"
        )

    if text.count("workflow_dispatch:") != 1:
        raise ArtifactWorkflowPolicyError("P6-V4 must expose exactly one owner dispatch trigger")
    if text.count("\n  push:\n") != 1:
        raise ArtifactWorkflowPolicyError("P6-V4 must expose exactly one trusted main push trigger")
    if text.count("runs-on:") != 1:
        raise ArtifactWorkflowPolicyError("P6-V4 must contain exactly one GitHub-hosted job")
    if text.count("retention-days: 14") != 1:
        raise ArtifactWorkflowPolicyError("P6-V4 must keep exactly one 14-day review artifact")


def _verify_gallery_payload() -> tuple[int, int, int]:
    package = build_mobile_review_package(build_reference_gallery())
    with TemporaryDirectory(prefix="tracepixel-p6-v4-") as temporary:
        output = Path(temporary) / "gallery"
        write_mobile_review_package(package, output)
        files = sorted(path.name for path in output.iterdir())
        if files != ["index.html", "index.ko.html", "manifest.json"]:
            raise AssertionError(f"P6-V4 gallery payload drifted: {files!r}")
        if (output / "index.html").read_bytes() != package.html_en:
            raise AssertionError("P6-V4 English publication input differs from deterministic P6-V5 package")
        if (output / "index.ko.html").read_bytes() != package.html_ko:
            raise AssertionError("P6-V4 Korean publication input differs from deterministic P6-V5 package")
        return (
            len(package.html_en),
            len(package.html_ko),
            (output / "manifest.json").stat().st_size,
        )


def main() -> int:
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    validate_workflow_policy(workflow_text)
    html_en_bytes, html_ko_bytes, manifest_bytes = _verify_gallery_payload()
    print(
        "P6-V4 trusted artifact publishing checkpoint passed: "
        f"triggers=main-push,owner-dispatch ref=main runner=ubuntu-latest retention_days=14 "
        f"html_en_bytes={html_en_bytes} html_ko_bytes={html_ko_bytes} manifest_bytes={manifest_bytes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
