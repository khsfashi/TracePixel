from __future__ import annotations

import json
from pathlib import Path

from tracepixel.benchmark import (
    B0_FREEZE_COMMIT,
    blind_review_key,
    build_b0_schedule,
    load_b0_preregistration,
    visible_task_packet,
)


ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "evidence" / "b0" / "preregistration.v1.json"


def main() -> int:
    preregistration, digest = load_b0_preregistration(FREEZE)
    schedule = build_b0_schedule(
        preregistration,
        preregistration_sha256=digest,
    )

    if schedule["freeze_commit"] != B0_FREEZE_COMMIT:
        raise RuntimeError("B0-F0 freeze commit drifted")
    if schedule["scheduled_attempt_count"] != 28:
        raise RuntimeError("frozen B0 cohort must materialize exactly 28 primary attempts")
    if len({attempt["attempt_id"] for attempt in schedule["attempts"]}) != 28:
        raise RuntimeError("scheduled attempt identities must be unique")
    if len({blind_review_key(attempt) for attempt in schedule["attempts"]}) != 28:
        raise RuntimeError("blind review keys must be unique across the frozen cohort")

    for task in preregistration["tasks"]:
        packet = visible_task_packet(preregistration, task["id"])
        if "hidden_structural_constraints" in packet:
            raise RuntimeError("matched provider-visible task packets leaked hidden constraints")

    summary = {
        "schema": "tracepixel.b0-h0-checkpoint.v1",
        "freeze_commit": B0_FREEZE_COMMIT,
        "preregistration_sha256": digest,
        "scheduled_attempts": schedule["scheduled_attempt_count"],
        "methods": [method["id"] for method in preregistration["scored_methods"]],
        "tasks": [task["id"] for task in preregistration["tasks"]],
        "provider_invocations": 0,
        "scored_attempts_started": 0,
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
