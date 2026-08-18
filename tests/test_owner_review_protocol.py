from __future__ import annotations

import copy
import unittest

from tracepixel.owner_review import (
    OwnerReviewValidationError,
    attach_owner_review_package,
    authorize_owner_run,
    begin_owner_run,
    freeze_owner_experiment,
    record_owner_review,
    validate_owner_review_session,
)


def _digest(character: str) -> str:
    return character * 64


def _frozen():
    return freeze_owner_experiment(
        experiment_id="p11-x1-test",
        task_id="p11-x1-static",
        asset_id="candidate-a",
        width=32,
        height=32,
        candidate_backends=["raw", "external", "tracepixel-direct"],
        request_ref="config/p11-x1/request.json",
        provider_model_ref="provider/model/revision:pinned",
        deterministic_checks=["structural.non_empty", "color.maximum_colors"],
        human_criteria=[
            {"id": "silhouette", "description": "Silhouette reads at native size."},
            {"id": "anatomy", "description": "Anatomy is believable for the target."},
            {"id": "material", "description": "Materials remain visually separable."},
        ],
        retention_prefix="evidence/p11_x1/test",
        budget={
            "max_provider_calls": 1,
            "max_input_tokens": 20000,
            "max_output_tokens": 4000,
            "max_wall_ms": 120000,
            "max_repair_attempts": 1,
            "max_regeneration_attempts": 0,
        },
    )


def _awaiting():
    session = authorize_owner_run(_frozen(), source_ref="issue:151#owner-run")
    session = begin_owner_run(session)
    return attach_owner_review_package(
        session,
        run={
            "run_id": "run-123",
            "provider_calls": 1,
            "input_tokens": 19000,
            "output_tokens": 3500,
            "wall_ms": 80000,
            "repair_attempts": 0,
            "regeneration_attempts": 0,
        },
        candidate_id="raw-run-123",
        backend="raw",
        candidate_rgba_sha256=_digest("a"),
        native_png={"ref": "artifact/native.png", "sha256": _digest("b")},
        preview_png={"ref": "artifact/preview.png", "sha256": _digest("c")},
        deterministic_qa_evidence={"ref": "artifact/qa.json", "sha256": _digest("d")},
        complexity_evidence={"ref": "artifact/complexity.json", "sha256": _digest("e")},
    )


class OwnerReviewProtocolTests(unittest.TestCase):
    def test_owner_authorization_is_required_before_run(self) -> None:
        with self.assertRaises(OwnerReviewValidationError) as raised:
            begin_owner_run(_frozen())
        self.assertEqual(raised.exception.code, "invalid_transition")

        authorized = authorize_owner_run(_frozen(), source_ref="issue:151#owner-run")
        self.assertEqual(authorized["state"], "ready-for-owner-run")
        self.assertEqual(authorized["owner_run_authorization"]["source_ref"], "issue:151#owner-run")
        self.assertEqual(begin_owner_run(authorized)["state"], "running")

    def test_review_package_enters_mandatory_owner_stop_with_exact_artifact_identity(self) -> None:
        session = _awaiting()
        self.assertEqual(session["state"], "awaiting-owner-review")
        self.assertEqual(session["run"]["run_id"], "run-123")
        self.assertEqual(session["review_package"]["native_png"]["sha256"], _digest("b"))
        self.assertIsNone(session["owner_review"])
        self.assertIsNone(session["feedback_intake"])

    def test_run_usage_cannot_exceed_frozen_budget(self) -> None:
        session = begin_owner_run(authorize_owner_run(_frozen(), source_ref="issue:151#owner-run"))
        with self.assertRaises(OwnerReviewValidationError) as raised:
            attach_owner_review_package(
                session,
                run={
                    "run_id": "run-over",
                    "provider_calls": 2,
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "wall_ms": 1,
                    "repair_attempts": 0,
                    "regeneration_attempts": 0,
                },
                candidate_id="raw-run-over",
                backend="raw",
                candidate_rgba_sha256=_digest("a"),
                native_png={"ref": "native.png", "sha256": _digest("b")},
                preview_png={"ref": "preview.png", "sha256": _digest("c")},
                deterministic_qa_evidence={"ref": "qa.json", "sha256": _digest("d")},
                complexity_evidence={"ref": "complexity.json", "sha256": _digest("e")},
            )
        self.assertEqual(raised.exception.code, "budget_exceeded")

    def test_frozen_experiment_digest_fails_closed_on_budget_mutation(self) -> None:
        session = _frozen()
        forged = copy.deepcopy(session)
        forged["experiment"]["budget"]["max_provider_calls"] = 99
        with self.assertRaises(OwnerReviewValidationError) as raised:
            validate_owner_review_session(forged)
        self.assertEqual(raised.exception.code, "experiment_digest_mismatch")

    def test_partial_owner_feedback_leaves_unspecified_criteria_unresolved(self) -> None:
        reviewed = record_owner_review(
            _awaiting(),
            source_ref="issue:151#owner-review",
            decision="request_repair",
            summary="Silhouette is good, anatomy is weak. Repair anatomy only from the stated feedback.",
            criterion_statuses={"silhouette": "accepted", "anatomy": "rejected"},
            repair_feedback=[
                {
                    "id": "owner-anatomy",
                    "summary": "Anatomy is weak.",
                    "stage_hint": None,
                    "region_hint": None,
                }
            ],
        )

        self.assertEqual(reviewed["state"], "repair-requested")
        statuses = {item["id"]: item["status"] for item in reviewed["owner_review"]["criteria"]}
        self.assertEqual(statuses["silhouette"], "accepted")
        self.assertEqual(statuses["anatomy"], "rejected")
        self.assertEqual(statuses["material"], "unresolved")

    def test_repair_feedback_reuses_p7_intake_and_binds_exact_native_png(self) -> None:
        reviewed = record_owner_review(
            _awaiting(),
            source_ref="issue:151#owner-review",
            decision="request_repair",
            summary="Owner requests one bounded repair.",
            repair_feedback=[
                {
                    "id": "owner-detail",
                    "summary": "The equipment attachment is unclear.",
                    "stage_hint": None,
                    "region_hint": None,
                }
            ],
        )
        intake = reviewed["feedback_intake"]
        self.assertEqual(intake["schema"], "tracepixel.feedback-intake.v1")
        self.assertEqual(intake["target"]["artifact_sha256"], _digest("b"))
        self.assertEqual(intake["items"][0]["authority"], "owner_human")
        self.assertTrue(intake["items"][0]["human"]["human_rejection"])
        self.assertIsNone(intake["items"][0]["stage_hint"])
        self.assertIsNone(intake["items"][0]["region_hint"])

    def test_overall_reject_can_stop_without_inventing_failed_criteria(self) -> None:
        reviewed = record_owner_review(
            _awaiting(),
            source_ref="issue:151#owner-review",
            decision="reject_stop",
            summary="REJECT.",
        )
        self.assertEqual(reviewed["state"], "rejected-stop")
        self.assertTrue(all(item["status"] == "unresolved" for item in reviewed["owner_review"]["criteria"]))
        self.assertIsNone(reviewed["feedback_intake"])

    def test_request_repair_requires_explicit_feedback_not_agent_invention(self) -> None:
        with self.assertRaises(OwnerReviewValidationError) as raised:
            record_owner_review(
                _awaiting(),
                source_ref="issue:151#owner-review",
                decision="request_repair",
                summary="REJECT.",
            )
        self.assertEqual(raised.exception.code, "repair_feedback_required")


if __name__ == "__main__":
    unittest.main()
