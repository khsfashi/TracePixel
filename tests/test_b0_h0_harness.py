from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from tracepixel.benchmark import (
    B0_FREEZE_COMMIT,
    B0HarnessContractError,
    applicable_structural_rules,
    blind_review_key,
    build_attempt_result,
    build_b0_schedule,
    json_payload,
    load_b0_preregistration,
    make_void_infrastructure_rerun,
    visible_task_packet,
    write_attempt_record,
)


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "evidence" / "b0" / "preregistration.v1.json"


class B0H0HarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.freeze, cls.freeze_digest = load_b0_preregistration(FREEZE)
        cls.schedule = build_b0_schedule(
            cls.freeze,
            preregistration_sha256=cls.freeze_digest,
        )

    def test_schedule_materializes_all_28_primary_attempts_once(self) -> None:
        schedule = self.schedule
        self.assertEqual(schedule["freeze_commit"], B0_FREEZE_COMMIT)
        self.assertEqual(schedule["scheduled_attempt_count"], 28)
        self.assertEqual(len(schedule["attempts"]), 28)
        self.assertEqual(
            len({attempt["attempt_id"] for attempt in schedule["attempts"]}),
            28,
        )
        self.assertTrue(all(attempt["rerun_index"] == 0 for attempt in schedule["attempts"]))
        self.assertTrue(all(attempt["rerun_of"] is None for attempt in schedule["attempts"]))

    def test_visible_task_packet_never_exposes_hidden_constraints(self) -> None:
        for task in self.freeze["tasks"]:
            packet = visible_task_packet(self.freeze, task["id"])
            self.assertEqual(packet["visible_text"], task["visible_text"])
            self.assertNotIn("hidden_structural_constraints", packet)
            self.assertEqual(
                set(packet),
                {"schema", "task_id", "tier", "visible_text"},
            )

    def test_noncompletion_scores_every_frozen_rule_as_zero(self) -> None:
        identity = self.schedule["attempts"][0]
        rules = applicable_structural_rules(self.freeze, identity["task_id"])
        result = build_attempt_result(
            self.freeze,
            identity=identity,
            provider_invoked=True,
            completion=False,
            failure_category="timeout",
            rule_results=None,
        )
        self.assertEqual(result["structural"]["applicable_rules"], len(rules))
        self.assertEqual(result["structural"]["passed_rules"], 0)
        self.assertEqual(result["structural"]["fraction_numerator"], 0)
        self.assertEqual(result["structural"]["fraction_denominator"], len(rules))
        self.assertFalse(result["structural"]["all_rules_pass"])
        self.assertEqual(result["structural"]["rule_results"], {rule: False for rule in rules})

    def test_partial_or_extra_structural_rule_sets_are_rejected(self) -> None:
        identity = self.schedule["attempts"][0]
        rules = applicable_structural_rules(self.freeze, identity["task_id"])
        with self.assertRaises(B0HarnessContractError):
            build_attempt_result(
                self.freeze,
                identity=identity,
                provider_invoked=True,
                completion=True,
                failure_category=None,
                rule_results={rules[0]: True},
            )

        complete = {rule: True for rule in rules}
        complete["invented_rule"] = True
        with self.assertRaises(B0HarnessContractError):
            build_attempt_result(
                self.freeze,
                identity=identity,
                provider_invoked=True,
                completion=True,
                failure_category=None,
                rule_results=complete,
            )

    def test_void_infrastructure_is_pre_invocation_and_allows_only_one_named_rerun(self) -> None:
        identity = self.schedule["attempts"][0]
        primary = build_attempt_result(
            self.freeze,
            identity=identity,
            provider_invoked=False,
            completion=False,
            failure_category="void_infrastructure",
            rule_results=None,
            infrastructure_void={
                "reason": "fixture setup defect before provider invocation",
                "fix_commit": "a" * 40,
            },
        )
        rerun = make_void_infrastructure_rerun(primary, self.freeze)
        self.assertEqual(rerun["rerun_index"], 1)
        self.assertEqual(rerun["rerun_of"], identity["attempt_id"])
        self.assertNotEqual(rerun["attempt_id"], identity["attempt_id"])

        with self.assertRaises(B0HarnessContractError):
            build_attempt_result(
                self.freeze,
                identity=identity,
                provider_invoked=True,
                completion=False,
                failure_category="void_infrastructure",
                rule_results=None,
                infrastructure_void={"reason": "too late", "fix_commit": "a" * 40},
            )

    def test_blind_review_key_matches_frozen_formula(self) -> None:
        identity = self.schedule["attempts"][3]
        expected = sha256(
            f"{identity['task_id']}|{identity['trial_index']}|{identity['method_id']}".encode("utf-8")
        ).hexdigest()
        self.assertEqual(blind_review_key(identity), expected)

    def test_attempt_writer_hashes_payloads_and_refuses_overwrite(self) -> None:
        identity = self.schedule["attempts"][0]
        result = build_attempt_result(
            self.freeze,
            identity=identity,
            provider_invoked=True,
            completion=False,
            failure_category="transport_provider_failure",
            rule_results=None,
        )
        payloads = {
            "provider-request.json": json_payload({"request": "retained"}),
            "provider-response.json": json_payload({"response": None, "transport_failure": True}),
            "proposal-or-failure.json": json_payload({"failure": "transport_provider_failure"}),
            "deterministic-qa.json": json_payload({"available": False}),
            "telemetry.json": json_payload({"failure_category": "transport_provider_failure"}),
        }

        with tempfile.TemporaryDirectory() as directory:
            output = write_attempt_record(directory, self.freeze, result, payloads)
            manifest = json.loads((output / "attempt-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["identity"]["freeze_commit"], B0_FREEZE_COMMIT)
            for name, payload in payloads.items():
                self.assertEqual(manifest["artifacts"][name]["sha256"], sha256(payload).hexdigest())
                self.assertEqual(manifest["artifacts"][name]["bytes"], len(payload))
                self.assertEqual((output / name).read_bytes(), payload)
            with self.assertRaises(FileExistsError):
                write_attempt_record(directory, self.freeze, result, payloads)


if __name__ == "__main__":
    unittest.main()
