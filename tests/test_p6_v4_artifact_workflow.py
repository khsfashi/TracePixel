from __future__ import annotations

from pathlib import Path
import unittest

from evidence.p6_v4.checkpoint import (
    ArtifactWorkflowPolicyError,
    validate_workflow_policy,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "trusted-gallery-artifact.yml"


class P6V4ArtifactWorkflowTests(unittest.TestCase):
    def _workflow(self) -> str:
        return WORKFLOW.read_text(encoding="utf-8")

    def test_committed_workflow_stays_inside_trusted_publication_boundary(self) -> None:
        validate_workflow_policy(self._workflow())

    def test_public_pr_trigger_is_rejected(self) -> None:
        text = self._workflow().replace("  workflow_dispatch:\n", "  workflow_dispatch:\n  pull_request:\n")
        with self.assertRaises(ArtifactWorkflowPolicyError):
            validate_workflow_policy(text)

    def test_self_hosted_runner_is_rejected(self) -> None:
        text = self._workflow().replace("runs-on: ubuntu-latest", "runs-on: [self-hosted, windows]")
        with self.assertRaises(ArtifactWorkflowPolicyError):
            validate_workflow_policy(text)

    def test_secret_reference_is_rejected(self) -> None:
        text = self._workflow().replace(
            "      - name: Install TracePixel\n",
            "      - name: Forbidden secret\n        run: echo ${{ secrets.TEST_TOKEN }}\n\n      - name: Install TracePixel\n",
        )
        with self.assertRaises(ArtifactWorkflowPolicyError):
            validate_workflow_policy(text)

    def test_write_permission_is_rejected(self) -> None:
        text = self._workflow().replace("contents: read", "contents: write")
        with self.assertRaises(ArtifactWorkflowPolicyError):
            validate_workflow_policy(text)

    def test_unapproved_action_surface_is_rejected(self) -> None:
        text = self._workflow().replace(
            "      - name: Install TracePixel\n",
            "      - name: Unapproved action\n        uses: vendor/action@v1\n\n      - name: Install TracePixel\n",
        )
        with self.assertRaises(ArtifactWorkflowPolicyError):
            validate_workflow_policy(text)


if __name__ == "__main__":
    unittest.main()
