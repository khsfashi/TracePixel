from pathlib import Path
import unittest


class P8B5OwnerRepairStatusWorkflowTests(unittest.TestCase):
    def test_callback_is_owner_scoped_github_hosted_and_action_free(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "p8-b5-owner-repair-status.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("workflow_run:", workflow)
        self.assertIn('workflows: ["Owner P8-B5 localized retained repair"]', workflow)
        self.assertIn("types: [completed]", workflow)
        self.assertIn("github.event.workflow_run.actor.login == github.repository_owner", workflow)
        self.assertIn("github.event.workflow_run.event == 'workflow_dispatch'", workflow)
        self.assertIn("github.event.workflow_run.event == 'issue_comment'", workflow)
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertNotIn("uses:", workflow)
        self.assertIn("issues/92/comments", workflow)
        self.assertIn("does not approve the pending owner visual gate", workflow)


if __name__ == "__main__":
    unittest.main()
