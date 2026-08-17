from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evidence.p8_b5.retained_authoring import run_retained_authoring
from evidence.p8_b5.retained_repair import (
    EXPECTED_SOURCE_ARTIFACT,
    EXPECTED_SOURCE_RUN_ID,
    OWNER_REVIEW_SCHEMA_V1,
    REPAIR_MEMBER_ID,
    run_retained_repair,
)
from tracepixel.agent import AGENT_PROVIDER_PROPOSAL_SCHEMA_V1, AgentProviderUsage


class _FullProvider:
    def __init__(self, *, terrain_color: tuple[int, int, int] = (90, 130, 70), hole: bool = False) -> None:
        self._usage = AgentProviderUsage(input_tokens=5, output_tokens=3)
        self._terrain_color = terrain_color
        self._hole = hole

    def propose(self, request, /):
        intent = request["observation"]["intent"]
        canvas = intent["canvas"]
        width = canvas["width"]
        height = canvas["height"]
        asset_class = intent["asset_class"]
        if asset_class == "terrain-tile":
            red, green, blue = self._terrain_color
            coords = [
                [x, y, red, green, blue, 255]
                for y in range(height)
                for x in range(width)
                if not (self._hole and x == width // 2 and y == height // 2)
            ]
        else:
            x0 = width // 2 - 2
            y0 = height // 2 - 2
            coords = [
                [x, y, 200, 70, 80, 255]
                for y in range(y0, y0 + 4)
                for x in range(x0, x0 + 4)
            ]
        return {
            "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
            "kind": "pixel_program",
            "payload": {
                "schema": "tracepixel.pixel-program.v1",
                "canvas": {"width": width, "height": height},
                "operations": [{"op": "set_pixels", "pixels": coords}],
            },
        }

    def last_usage(self, /) -> AgentProviderUsage:
        return self._usage


class _BaselineProvider(_FullProvider):
    pass


class _ChangedRepairProvider(_FullProvider):
    def __init__(self) -> None:
        super().__init__(terrain_color=(105, 145, 82))


class _HoleRepairProvider(_FullProvider):
    def __init__(self) -> None:
        super().__init__(terrain_color=(105, 145, 82), hole=True)


class _CountingFactory:
    def __init__(self, provider_type: type[_FullProvider]) -> None:
        self.provider_type = provider_type
        self.calls = 0

    def __call__(self) -> object:
        self.calls += 1
        return self.provider_type()


def _manifest(root: Path, member_id: str) -> dict[str, object]:
    return json.loads((root / "members" / member_id / "manifest.json").read_text(encoding="utf-8"))


def _synthetic_gate(source: Path) -> dict[str, object]:
    member_ids = sorted(path.name for path in (source / "members").iterdir() if path.is_dir())
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for member_id in member_ids:
        manifest = _manifest(source, member_id)
        record: dict[str, object] = {
            "member_id": member_id,
            "request_sha256": manifest["request_sha256"],
            "final_png_sha256": manifest["final_png_sha256"],
        }
        if member_id == REPAIR_MEMBER_ID:
            record["feedback"] = "visible hole / missing-pixel defect"
            record["action"] = "re-author-member-only"
            rejected.append(record)
        else:
            accepted.append(record)
    return {
        "schema": OWNER_REVIEW_SCHEMA_V1,
        "recorded": "2026-08-17",
        "source_issue": 92,
        "source_run_id": EXPECTED_SOURCE_RUN_ID,
        "source_artifact_name": EXPECTED_SOURCE_ARTIFACT,
        "source_artifact_sha256": "0" * 64,
        "review_scope": "retained-output",
        "verdict": "partial-accept-repair-required",
        "accepted_members": accepted,
        "rejected_members": rejected,
    }


class P8B5RetainedRepairTests(unittest.TestCase):
    def test_only_rejected_member_is_reauthored_and_accepted_siblings_are_byte_preserved(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            output = root / "repair"
            run_retained_authoring(source, _BaselineProvider)
            gate = _synthetic_gate(source)
            before = {
                record["member_id"]: record["final_png_sha256"]
                for record in gate["accepted_members"]
            }
            rejected_before = gate["rejected_members"][0]["final_png_sha256"]

            factory = _CountingFactory(_ChangedRepairProvider)
            summary = run_retained_repair(source, output, factory, review_gate=gate)

            self.assertEqual(factory.calls, 1)
            self.assertEqual(summary["review_scope"], "retained-output")
            self.assertEqual(summary["member_count"], 8)
            self.assertEqual(summary["preserved_member_count"], 7)
            self.assertEqual(summary["repair_member_id"], REPAIR_MEMBER_ID)
            self.assertEqual(summary["repair_declared_max_concurrency"], 1)
            self.assertEqual(summary["repair_provider_calls"], 1)
            self.assertEqual(summary["source_aggregate_provider_calls"], 8)
            self.assertEqual(summary["effective_aggregate_provider_calls"], 9)
            self.assertTrue(summary["replacement_changed"])
            self.assertTrue(summary["repair_constraint_satisfied"])
            self.assertEqual(summary["owner_verdict"], "pending")
            self.assertTrue(summary["owner_review_required_before_p8_b6"])

            for member_id, digest in before.items():
                self.assertEqual(_manifest(output, member_id)["final_png_sha256"], digest)
                self.assertEqual(
                    (output / "members" / member_id / "final.png").read_bytes(),
                    (source / "members" / member_id / "final.png").read_bytes(),
                )
            self.assertNotEqual(_manifest(output, REPAIR_MEMBER_ID)["final_png_sha256"], rejected_before)

            repair_record = json.loads((output / "repair-record.json").read_text(encoding="utf-8"))
            self.assertEqual(repair_record["repair_member_id"], REPAIR_MEMBER_ID)
            self.assertEqual(len(repair_record["preserved_members"]), 7)
            self.assertTrue(repair_record["completion_constraint_satisfied"])
            self.assertNotEqual(
                repair_record["prior_request_sha256"],
                repair_record["repair_request_sha256"],
            )

            review_manifest = json.loads(
                (output / "review-package" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(review_manifest["review_scope"], "retained-output")
            self.assertEqual(len(review_manifest["members"]), 8)
            self.assertTrue((output / "review-package" / "index.html").is_file())
            self.assertTrue((output / "review-package" / "index.ko.html").is_file())

    def test_source_digest_drift_blocks_provider_invocation(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            output = root / "repair"
            run_retained_authoring(source, _BaselineProvider)
            gate = _synthetic_gate(source)
            accepted_id = gate["accepted_members"][0]["member_id"]
            (source / "members" / accepted_id / "final.png").write_bytes(b"tampered")

            factory = _CountingFactory(_ChangedRepairProvider)
            with self.assertRaises(SystemExit):
                run_retained_repair(source, output, factory, review_gate=gate)
            self.assertEqual(factory.calls, 0)

    def test_owner_hole_regression_fails_even_when_standard_qa_can_pass(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            output = root / "repair"
            run_retained_authoring(source, _BaselineProvider)
            gate = _synthetic_gate(source)

            factory = _CountingFactory(_HoleRepairProvider)
            with self.assertRaisesRegex(SystemExit, "completion constraint failed"):
                run_retained_repair(source, output, factory, review_gate=gate)
            self.assertEqual(factory.calls, 1)

    def test_owner_repair_workflow_is_main_owner_only_and_pinned_to_reviewed_run(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "owner-p8-b5-retained-repair.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("github.actor == github.repository_owner", workflow)
        self.assertIn("runs-on: [self-hosted, Windows, X64]", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("actions: read", workflow)
        self.assertIn("32022902199", workflow)
        self.assertIn("9286172654", workflow)
        self.assertIn("p8-b5-retained-authoring-32022902199", workflow)
        self.assertIn("git -C $env:GITHUB_WORKSPACE fetch --depth=1 origin $env:GITHUB_SHA", workflow)
        self.assertIn("Invoke-WebRequest", workflow)
        self.assertNotIn("actions/checkout@", workflow)
        self.assertNotIn("actions/setup-python@", workflow)
        self.assertNotIn("actions/download-artifact@", workflow)
        self.assertEqual(workflow.count("uses:"), 1)
        self.assertIn("uses: actions/upload-artifact@v4", workflow)
        self.assertIn("Logged in using ChatGPT", workflow)
        self.assertIn("Logged in using an API key", workflow)
        self.assertIn("owner_verdict -ne \"pending\"", workflow)


if __name__ == "__main__":
    unittest.main()
