from __future__ import annotations

from tracepixel.owner_review import (
    attach_owner_review_package,
    authorize_owner_run,
    begin_owner_run,
    freeze_owner_experiment,
    record_owner_review,
)


def _digest(character: str) -> str:
    return character * 64


def main() -> int:
    session = freeze_owner_experiment(
        experiment_id="p11-x1-checkpoint",
        task_id="p11-x1-owner-loop",
        asset_id="p11-x1-candidate",
        width=32,
        height=32,
        candidate_backends=["raw", "external", "tracepixel-direct"],
        request_ref="evidence/p11_x1/frozen-request",
        provider_model_ref="provider/model/revision:pinned-before-run",
        deterministic_checks=["structural.non_empty"],
        human_criteria=[
            {"id": "silhouette", "description": "Silhouette is readable."},
            {"id": "anatomy", "description": "Anatomy is believable."},
            {"id": "material", "description": "Materials are readable."},
        ],
        retention_prefix="evidence/p11_x1/retained",
        budget={
            "max_provider_calls": 1,
            "max_input_tokens": 20000,
            "max_output_tokens": 4000,
            "max_wall_ms": 120000,
            "max_repair_attempts": 1,
            "max_regeneration_attempts": 0,
        },
    )
    if session["state"] != "experiment-frozen":
        raise SystemExit("P11-X1 checkpoint failed: experiment did not freeze")

    session = authorize_owner_run(session, source_ref="issue:151#checkpoint-owner-run")
    session = begin_owner_run(session)
    session = attach_owner_review_package(
        session,
        run={
            "run_id": "retained-run-1",
            "provider_calls": 1,
            "input_tokens": 19000,
            "output_tokens": 3500,
            "wall_ms": 80000,
            "repair_attempts": 0,
            "regeneration_attempts": 0,
        },
        candidate_id="raw-retained-run-1",
        backend="raw",
        candidate_rgba_sha256=_digest("a"),
        native_png={"ref": "retained/native.png", "sha256": _digest("b")},
        preview_png={"ref": "retained/preview.png", "sha256": _digest("c")},
        deterministic_qa_evidence={"ref": "retained/qa.json", "sha256": _digest("d")},
        complexity_evidence={"ref": "retained/complexity.json", "sha256": _digest("e")},
    )
    if session["state"] != "awaiting-owner-review":
        raise SystemExit("P11-X1 checkpoint failed: review package did not stop for owner")

    reviewed = record_owner_review(
        session,
        source_ref="issue:151#checkpoint-owner-review",
        decision="request_repair",
        summary="Silhouette is acceptable but anatomy needs one bounded repair.",
        criterion_statuses={"silhouette": "accepted", "anatomy": "rejected"},
        repair_feedback=[
            {
                "id": "owner-anatomy",
                "summary": "Anatomy needs repair.",
                "stage_hint": None,
                "region_hint": None,
            }
        ],
    )
    if reviewed["state"] != "repair-requested":
        raise SystemExit("P11-X1 checkpoint failed: owner repair decision was not retained")
    statuses = {item["id"]: item["status"] for item in reviewed["owner_review"]["criteria"]}
    if statuses["material"] != "unresolved":
        raise SystemExit("P11-X1 checkpoint failed: unspecified owner criterion was invented")
    intake = reviewed["feedback_intake"]
    if intake["target"]["artifact_sha256"] != _digest("b"):
        raise SystemExit("P11-X1 checkpoint failed: feedback is not bound to exact reviewed artifact")
    if intake["items"][0]["stage_hint"] is not None or intake["items"][0]["region_hint"] is not None:
        raise SystemExit("P11-X1 checkpoint failed: unstated repair hints were invented")

    print("P11-X1 owner-operated review protocol checkpoint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
