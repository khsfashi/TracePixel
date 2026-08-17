from __future__ import annotations

from pathlib import Path
import unittest

from tracepixel.benchmark.b1_harness import build_b1_schedule, load_b1_preregistration
from tracepixel.benchmark.b1_scored import (
    B1_ATTEMPT_RECORD_SCHEMA_V1,
    B1_RAW_METHOD_ID,
    B1_TRACEPIXEL_METHOD_ID,
    B1ScoredContractError,
    build_b1_attempt_record,
)
from tracepixel.model import STAGE_SEQUENCE_V1

ROOT = Path(__file__).resolve().parents[1]
B1_PREREGISTRATION = ROOT / "evidence" / "b1" / "preregistration.v1.json"


def _stage_decisions(count: int = 6) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for index, stage in enumerate(STAGE_SEQUENCE_V1[:count]):
        if index % 2 == 0:
            result.append({"stage": stage, "status": "applied", "skip_reason": None})
        else:
            result.append(
                {
                    "stage": stage,
                    "status": "skipped",
                    "skip_reason": "No additional stage-local edit was required.",
                }
            )
    return result


def _qa() -> dict[str, object]:
    return {
        "schema": "tracepixel.b1-deterministic-qa.test.v1",
        "all_rules_pass": True,
        "rule_results": {"width": True},
    }


def _complexity() -> dict[str, object]:
    return {
        "schema": "tracepixel.b1-complexity.test.v1",
        "provider_calls": 6,
        "operation_calls": 6,
        "repair_cycles": 0,
    }


class B1S0CompletionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration, preregistration_sha256 = load_b1_preregistration(B1_PREREGISTRATION)
        schedule = build_b1_schedule(cls.preregistration, preregistration_sha256=preregistration_sha256)
        cls.tracepixel_identity = next(
            item for item in schedule["attempts"] if item["method_id"] == B1_TRACEPIXEL_METHOD_ID
        )
        cls.raw_identity = next(item for item in schedule["attempts"] if item["method_id"] == B1_RAW_METHOD_ID)

    def test_tracepixel_completion_requires_all_six_explicit_stage_decisions(self) -> None:
        with self.assertRaises(B1ScoredContractError) as caught:
            build_b1_attempt_record(
                self.preregistration,
                identity=self.tracepixel_identity,
                completion=True,
                failure_category=None,
                deterministic_qa=_qa(),
                complexity=_complexity(),
                stage_decisions=_stage_decisions(5),
            )
        self.assertEqual(caught.exception.code, "incomplete_stage_coverage")

    def test_tracepixel_completion_keeps_authority_layers_separate(self) -> None:
        record = build_b1_attempt_record(
            self.preregistration,
            identity=self.tracepixel_identity,
            completion=True,
            failure_category=None,
            deterministic_qa=_qa(),
            complexity=_complexity(),
            stage_decisions=_stage_decisions(),
        )
        self.assertEqual(record["schema"], B1_ATTEMPT_RECORD_SCHEMA_V1)
        self.assertTrue(record["completion"])
        self.assertTrue(record["stage_coverage"]["authoring_complete"])
        self.assertEqual(record["stage_coverage"]["decided_stages"], 6)
        self.assertEqual(record["stage_coverage"]["applied_stages"], 3)
        self.assertEqual(record["stage_coverage"]["skipped_stages"], 3)
        self.assertEqual(record["deterministic_qa"]["all_rules_pass"], True)
        self.assertEqual(record["repair"]["available"], False)
        self.assertEqual(record["complexity"]["provider_calls"], 6)

    def test_failed_tracepixel_attempt_preserves_partial_stage_prefix(self) -> None:
        record = build_b1_attempt_record(
            self.preregistration,
            identity=self.tracepixel_identity,
            completion=False,
            failure_category="budget_exhaustion",
            deterministic_qa=None,
            complexity=_complexity(),
            stage_decisions=_stage_decisions(2),
        )
        self.assertFalse(record["completion"])
        self.assertFalse(record["stage_coverage"]["authoring_complete"])
        self.assertEqual(record["stage_coverage"]["decided_stages"], 2)
        self.assertEqual(record["failure_category"], "budget_exhaustion")

    def test_stage_decisions_must_follow_frozen_order_and_skip_semantics(self) -> None:
        decisions = _stage_decisions()
        decisions[0] = {"stage": "major_forms", "status": "applied", "skip_reason": None}
        with self.assertRaises(B1ScoredContractError) as caught:
            build_b1_attempt_record(
                self.preregistration,
                identity=self.tracepixel_identity,
                completion=True,
                failure_category=None,
                deterministic_qa=_qa(),
                complexity=_complexity(),
                stage_decisions=decisions,
            )
        self.assertEqual(caught.exception.code, "invalid_stage_order")

    def test_raw_baseline_cannot_receive_tracepixel_stage_or_repair_surface(self) -> None:
        with self.assertRaises(B1ScoredContractError) as caught:
            build_b1_attempt_record(
                self.preregistration,
                identity=self.raw_identity,
                completion=True,
                failure_category=None,
                deterministic_qa=_qa(),
                complexity=_complexity(),
                stage_decisions=_stage_decisions(1),
            )
        self.assertEqual(caught.exception.code, "raw_stage_surface_forbidden")

    def test_b0_result_paths_are_rejected_from_retained_b1_layers(self) -> None:
        complexity = _complexity()
        complexity["seed_path"] = "evidence\\b0\\results\\frozen\\attempt\\final.rgba"
        with self.assertRaises(B1ScoredContractError) as caught:
            build_b1_attempt_record(
                self.preregistration,
                identity=self.tracepixel_identity,
                completion=True,
                failure_category=None,
                deterministic_qa=_qa(),
                complexity=complexity,
                stage_decisions=_stage_decisions(),
            )
        self.assertEqual(caught.exception.code, "b0_result_reference")


if __name__ == "__main__":
    unittest.main()
