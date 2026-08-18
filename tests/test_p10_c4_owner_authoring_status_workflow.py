from pathlib import Path
import unittest


class P10C4OwnerAuthoringStatusWorkflowTests(unittest.TestCase):
    def test_callback_is_owner_scoped_github_hosted_and_reports_artifacts_without_approval(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "p10-c4-owner-authoring-status.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("workflow_run:", workflow)
        self.assertIn('workflows: ["Owner P10-C4 retained creature authoring"]', workflow)
        self.assertIn("types: [completed]", workflow)
        self.assertIn("github.event.workflow_run.actor.login == github.repository_owner", workflow)
        self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertIn("github.event.workflow_run.event == 'workflow_dispatch'", workflow)
        self.assertIn("github.event.workflow_run.event == 'issue_comment'", workflow)
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertIn("actions: read", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertNotIn("self-hosted", workflow)
        self.assertNotIn("uses:", workflow)
        self.assertIn("actions/runs/{run_id}/artifacts?per_page=100", workflow)
        self.assertIn("issues/109/comments", workflow)
        self.assertIn("artifact id", workflow)
        self.assertIn("`owner_verdict` remains `pending`", workflow)
        self.assertIn("does not approve P10-C5 aesthetics or promotion", workflow)


if __name__ == "__main__":
    unittest.main()
