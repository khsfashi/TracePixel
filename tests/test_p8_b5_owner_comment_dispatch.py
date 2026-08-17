from pathlib import Path
import unittest


class P8B5OwnerCommentDispatchTests(unittest.TestCase):
    def test_issue_comment_trigger_is_exact_owner_only_and_never_public_runner_input(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "owner-p8-b5-retained-repair.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("issue_comment:", workflow)
        self.assertIn("types: [created]", workflow)
        self.assertIn("github.event_name == 'issue_comment'", workflow)
        self.assertIn("github.actor == github.repository_owner", workflow)
        self.assertIn("github.event.issue.number == 92", workflow)
        self.assertIn("github.event.comment.body == '/tracepixel owner-p8-b5-repair'", workflow)
        self.assertIn("runs-on: [self-hosted, Windows, X64]", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("pull_request_target:", workflow)


if __name__ == "__main__":
    unittest.main()
