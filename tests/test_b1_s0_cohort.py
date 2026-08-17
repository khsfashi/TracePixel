from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence.b1_s0.run import (
    _claim,
    _reconcile_claims,
    _retained,
    preflight_cohort,
    run_cohort,
)
from tracepixel.benchmark.b1_adapters import B1_TRACEPIXEL_METHOD_ID, B1CodexCall
from tracepixel.benchmark.b1_harness import (
    B1_EXPECTED_ATTEMPTS,
    B1_FREEZE_COMMIT,
    attempt_relative_path,
    build_b1_schedule,
    load_b1_preregistration,
)

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "evidence/b1/preregistration.v1.json"
FREEZE = ROOT / "evidence/b1/freeze.v1.json"
B0 = ROOT / "evidence/b0/preregistration.v1.json"
COMMIT = "a" * 40


def _program() -> dict[str, object]:
    pixels = [[x, y, 128, 32, 192, 255] for y in range(6, 10) for x in range(6, 10)]
    return {
        "schema": "tracepixel.pixel-program.v1",
        "canvas": {"width": 16, "height": 16},
        "operations": [{"op": "set_pixels", "pixels": pixels}],
    }


def _b1_s0_lane(root: Path) -> Path:
    path = root / "lane.json"
    path.write_text(
        json.dumps({"current": "B1", "current_child": "B1-S0", "active_issue": 79}),
        encoding="utf-8",
    )
    return path


class FakeExecutor:
    def __init__(self) -> None:
        self.preflights = 0
        self.invocations = 0

    def preflight(self, request):
        self.preflights += 1
        provider = request["provider"]
        return {
            "provider_surface": provider["provider_surface"],
            "auth_mode": "chatgpt",
            "codex_cli_version": provider["codex_cli_version"],
            "model": provider["model"],
        }

    def invoke(self, request, *, call_index: int) -> B1CodexCall:
        del call_index
        self.invocations += 1
        program = _program()
        output: object = (
            {"schema": "tracepixel.agent-provider-proposal.v1", "kind": "pixel_program", "payload": program}
            if request["attempt"]["method_id"] == B1_TRACEPIXEL_METHOD_ID
            else program
        )
        raw = json.dumps(output)
        return B1CodexCall("response", output, raw, 100, 20, 0, 1, 0, None)


def _write_complete(root: Path, identity: dict[str, object]) -> None:
    directory = root / attempt_relative_path(identity)
    directory.mkdir(parents=True)
    payloads = {
        "attempt-record.json": (json.dumps({"attempt": identity}) + "\n").encode(),
        "provider-request.json": b"{}\n",
        "provider-response.json": b"{}\n",
        "proposal-or-failure.json": b"{}\n",
        "deterministic-qa.json": b"{}\n",
        "complexity.json": b"{}\n",
    }
    for name, payload in payloads.items():
        (directory / name).write_bytes(payload)
    index = {
        "schema": "tracepixel.b1-retention-index.v1",
        "attempt_id": identity["attempt_id"],
        "files": {
            name: {"sha256": sha256(payload).hexdigest(), "bytes": len(payload)}
            for name, payload in payloads.items()
        },
    }
    (directory / "retention-index.json").write_text(json.dumps(index), encoding="utf-8")


class B1S0CohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prereg, digest = load_b1_preregistration(PREREG)
        cls.schedule = build_b1_schedule(cls.prereg, preregistration_sha256=digest)

    def test_preflight_only_does_not_invoke_scored_provider(self) -> None:
        executor = FakeExecutor()
        with tempfile.TemporaryDirectory() as temporary:
            lane = _b1_s0_lane(Path(temporary))
            with patch("evidence.b1_s0.run._source_guard"), patch(
                "evidence.b1_s0.run._runner_commit", return_value=COMMIT
            ):
                result = preflight_cohort(PREREG, FREEZE, B0, lane, executor=executor)
        self.assertEqual(1, executor.preflights)
        self.assertEqual(0, executor.invocations)
        self.assertFalse(result["provider_invoked"])
        self.assertEqual(B1_EXPECTED_ATTEMPTS, result["scheduled_attempt_count"])

    def test_durable_claim_blocks_automatic_rerun_without_complete_retention(self) -> None:
        identity = self.schedule["attempts"][0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim = _claim(root, identity, COMMIT)
            with self.assertRaises(SystemExit):
                _reconcile_claims(root, self.schedule)
            self.assertTrue(claim.is_file())

    def test_completed_retention_reconciles_stale_claim(self) -> None:
        identity = self.schedule["attempts"][0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim = _claim(root, identity, COMMIT)
            _write_complete(root, identity)
            _reconcile_claims(root, self.schedule)
            self.assertFalse(claim.exists())
            self.assertEqual(1, len(_retained(root, self.schedule)))

    def test_fake_full_cohort_writes_exact_schedule_and_blind_review(self) -> None:
        executor = FakeExecutor()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results, review = root / "results", root / "review"
            lane = _b1_s0_lane(root)
            with patch("evidence.b1_s0.run._source_guard"), patch(
                "evidence.b1_s0.run._runner_commit", return_value=COMMIT
            ):
                summary = run_cohort(PREREG, FREEZE, B0, lane, results, review, executor=executor)
            self.assertEqual(B1_EXPECTED_ATTEMPTS, summary["retained_attempt_count"])
            self.assertEqual(B1_EXPECTED_ATTEMPTS, summary["blind_review_entry_count"])
            self.assertEqual(1, executor.preflights)
            self.assertEqual(14 * 6 + 14, executor.invocations)
            self.assertEqual([], list((results / B1_FREEZE_COMMIT / ".claims").glob("*.json")))
            self.assertTrue((results / B1_FREEZE_COMMIT / "cohort-summary.json").is_file())
            self.assertTrue((review / B1_FREEZE_COMMIT / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
