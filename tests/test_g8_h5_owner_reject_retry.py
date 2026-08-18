from __future__ import annotations

from hashlib import sha256
import json
import tempfile
from pathlib import Path
import unittest

from evidence.g8_h5.retry_authoring import H5_REQUIRED_APPROVALS, RETRY_INSTRUCTION, run_retry, validate_owner_review
from tracepixel.agent import AGENT_PROVIDER_PROPOSAL_SCHEMA_V1, AgentProviderUsage
from tracepixel.model import PIXEL_PROGRAM_SCHEMA_V1

ROOT = Path(__file__).resolve().parents[1]
NEGATIVE = ROOT / "evidence" / "g8_h5" / "negative-evidence" / "32111680356"


class _Provider:
    def __init__(self) -> None:
        self.calls = 0
        self.requests = []
        self._usage = None

    def propose(self, request):
        self.calls += 1
        self.requests.append(request)
        self._usage = AgentProviderUsage(input_tokens=800, output_tokens=250)
        pixels = [[x, y, 60, 90, 110, 255] for y in range(10, 14) for x in range(10, 14)]
        return {
            "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
            "kind": "pixel_program",
            "payload": {
                "schema": PIXEL_PROGRAM_SCHEMA_V1,
                "canvas": {"width": 32, "height": 32},
                "operations": [{"op": "set_pixels", "pixels": pixels}],
            },
        }

    def last_usage(self, /):
        return self._usage


class G8H5Tests(unittest.TestCase):
    def test_owner_reject_is_retained(self) -> None:
        final = NEGATIVE / "final.png"
        self.assertEqual(
            sha256(final.read_bytes()).hexdigest(),
            "35af63e33ea7d319a92aacbede1e641a4a1ca6aac7f428277e32bc0fb9e23d82",
        )
        verdict = json.loads((NEGATIVE / "verdict.json").read_text(encoding="utf-8"))
        self.assertEqual(verdict["owner_verdict"], "reject")
        self.assertEqual(verdict["technical_execution"], "valid")
        self.assertEqual(verdict["product_quality_promotion"], "failed")
        complexity = json.loads((NEGATIVE / "complexity.json").read_text(encoding="utf-8"))
        self.assertEqual((complexity["candidate_run_id"], complexity["provider_calls"]), (32111680356, 5))
        self.assertEqual((complexity["input_tokens"], complexity["output_tokens"]), (91917, 19060))

    def test_retry_is_one_shot_cost_guarded_and_never_self_promotes(self) -> None:
        provider = _Provider()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "retry"
            summary = run_retry(output, lambda: provider, source_sha="2" * 40)
            self.assertEqual(provider.calls, 1)
            instruction = provider.requests[0]["instruction"]
            self.assertTrue(instruction.startswith(RETRY_INSTRUCTION))
            self.assertIn("BOUND_HUMANOID_CONTEXT=", instruction)
            self.assertIn("orientation_intent", instruction)
            self.assertIn("equipment_attachments", instruction)
            self.assertEqual(summary["status"], "awaiting-owner-review")
            self.assertEqual(summary["owner_verdict"], "pending")
            self.assertFalse(summary["deterministic_qa_is_visual_quality_success"])
            self.assertEqual(summary["provider_repair_calls_allowed"], 0)
            self.assertEqual(tuple(summary["h5_required_approvals"]), H5_REQUIRED_APPROVALS))
            guard = json.loads((output / "quality-per-cost-guard.json").read_text(encoding="utf-8"))
            self.assertTrue(guard["passed"])
            complexity = json.loads((output / "complexity.json").read_text(encoding="utf-8"))
            self.assertEqual(complexity["repair_vs_regeneration"]["repair_provider_calls"], 0)

    def test_owner_accept_requires_all_seven(self) -> None:
        approved = {name: True for name in H5_REQUIRD_APPROVALS}
        self.assertTrue(validate_owner_review(approved))
        for name in H5_REQUIRD_APPROVALS:
            rejected = dict(approved)
            rejected[name] = False
            self.assertFalse(validate_owner_review(rejected))

    def test_brief_contains_fixed_fixture_requirements(self) -> None:
        for phrase in (
            "three-quarter-right",
            "negative-space gaps",
            "touch/overlap",
            "matte teal cloth",
            "dark-brown leather",
            "high side-plume",
            "coherent 2-4px clusters",
        ):
            self.assertIn(phrase, RETRY_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
