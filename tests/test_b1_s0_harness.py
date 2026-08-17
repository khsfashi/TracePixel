from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tracepixel.benchmark.b1_harness import (
    B1_EXPECTED_ATTEMPTS,
    B1_FREEZE_COMMIT,
    B1HarnessContractError,
    assert_b1_is_held_out,
    attempt_relative_path,
    build_b1_schedule,
    load_b1_freeze_record,
    load_b1_preregistration,
    validate_b1_attempt_identity,
)

ROOT = Path(__file__).resolve().parents[1]
B1_PREREGISTRATION = ROOT / "evidence" / "b1" / "preregistration.v1.json"
B1_FREEZE_RECORD = ROOT / "evidence" / "b1" / "freeze.v1.json"
B0_PREREGISTRATION = ROOT / "evidence" / "b0" / "preregistration.v1.json"


class B1S0HarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.b1, cls.b1_sha256 = load_b1_preregistration(B1_PREREGISTRATION)
        cls.freeze = load_b1_freeze_record(B1_FREEZE_RECORD)
        cls.b0 = json.loads(B0_PREREGISTRATION.read_text(encoding="utf-8"))

    def test_recorded_freeze_is_exact_pr81_merge(self) -> None:
        self.assertEqual(self.freeze["freeze_commit"], B1_FREEZE_COMMIT)
        self.assertEqual(self.freeze["source_pr"], 81)
        self.assertEqual(self.freeze["preregistration_path"], "evidence/b1/preregistration.v1.json")

    def test_schedule_is_exactly_two_trials_for_seven_tasks_and_two_methods(self) -> None:
        schedule = build_b1_schedule(self.b1, preregistration_sha256=self.b1_sha256)
        attempts = schedule["attempts"]
        self.assertEqual(schedule["scheduled_attempt_count"], B1_EXPECTED_ATTEMPTS)
        self.assertEqual(len(attempts), 28)
        self.assertEqual(len({item["attempt_id"] for item in attempts}), 28)
        self.assertEqual(len({attempt_relative_path(item).as_posix() for item in attempts}), 28)
        for identity in attempts:
            validated = validate_b1_attempt_identity(identity, self.b1)
            self.assertEqual(validated["freeze_commit"], B1_FREEZE_COMMIT)

    def test_b1_tasks_remain_held_out_from_b0(self) -> None:
        assert_b1_is_held_out(self.b1, self.b0)
        mutated = deepcopy(self.b1)
        mutated["tasks"][0]["visible_text"] = self.b0["tasks"][0]["visible_text"]
        with self.assertRaises(B1HarnessContractError) as caught:
            assert_b1_is_held_out(mutated, self.b0)
        self.assertEqual(caught.exception.code, "b0_text_reuse")

    def test_attempt_path_is_freeze_rooted_and_rejects_path_escape(self) -> None:
        schedule = build_b1_schedule(self.b1, preregistration_sha256=self.b1_sha256)
        identity = schedule["attempts"][0]
        path = attempt_relative_path(identity)
        self.assertEqual(path.parts[0], B1_FREEZE_COMMIT)
        self.assertNotIn("b0", {part.lower() for part in path.parts})
        unsafe = dict(identity)
        unsafe["method_id"] = "../escape"
        with self.assertRaises(B1HarnessContractError) as caught:
            attempt_relative_path(unsafe)
        self.assertEqual(caught.exception.code, "unsafe_path_component")

    def test_identity_refuses_wrong_freeze_commit(self) -> None:
        schedule = build_b1_schedule(self.b1, preregistration_sha256=self.b1_sha256)
        identity = dict(schedule["attempts"][0])
        identity["freeze_commit"] = "0" * 40
        with self.assertRaises(B1HarnessContractError) as caught:
            validate_b1_attempt_identity(identity, self.b1)
        self.assertEqual(caught.exception.code, "freeze_commit_mismatch")


if __name__ == "__main__":
    unittest.main()
