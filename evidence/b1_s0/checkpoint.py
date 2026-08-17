from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from tracepixel.benchmark.b1_harness import (
    B1_EXPECTED_ATTEMPTS,
    B1_FREEZE_COMMIT,
    B1_REPOSITORY_COMMIT_UNDER_TEST,
    B1_SCORED_METHOD_IDS,
    assert_b1_is_held_out,
    attempt_relative_path,
    build_b1_schedule,
    load_b1_freeze_record,
    load_b1_preregistration,
    validate_b1_attempt_identity,
)

ROOT = Path(__file__).resolve().parents[2]
B1_PREREGISTRATION = ROOT / "evidence" / "b1" / "preregistration.v1.json"
B1_FREEZE_RECORD = ROOT / "evidence" / "b1" / "freeze.v1.json"
B1_POSTMORTEM = ROOT / "evidence" / "b1" / "postmortem.v1.json"
B0_PREREGISTRATION = ROOT / "evidence" / "b0" / "preregistration.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _validate_lane(lane: dict[str, object]) -> None:
    current, child, issue = lane.get("current"), lane.get("current_child"), lane.get("active_issue")
    if current == "B1":
        if child not in {"B1-S0", "B1-P0"} or issue != 79:
            raise SystemExit("active B1 checkpoint requires B1-S0/B1-P0 on issue #79")
        return

    sequence = lane.get("sequence")
    if type(sequence) is not list or type(current) is not str or "P8" not in sequence or current not in sequence:
        raise SystemExit("B1-S0 checkpoint requires the live core lane to remain at B1 or later")
    phases = cast(list[object], sequence)
    if phases.index(current) < phases.index("P8"):
        raise SystemExit("B1-S0 checkpoint cannot move behind the B1-to-P8 handoff")

    post = _json(B1_POSTMORTEM)
    if post.get("schema") != "tracepixel.b1-postmortem.v1" or post.get("status") != "frozen-complete":
        raise SystemExit("post-B1 lane requires the frozen B1-P0 postmortem")
    if current == "P8":
        children = cast(dict[str, object], lane.get("child_sequences", {})).get("P8")
        if type(children) is not list or child not in children or issue != 92:
            raise SystemExit("active P8 work must remain on issue #92 and a declared P8 child")


def main() -> int:
    preregistration, preregistration_sha256 = load_b1_preregistration(B1_PREREGISTRATION)
    freeze = load_b1_freeze_record(B1_FREEZE_RECORD)
    b0 = _json(B0_PREREGISTRATION)
    lane = _json(CORE_LANE)

    _validate_lane(lane)
    if freeze["freeze_commit"] != B1_FREEZE_COMMIT:
        raise SystemExit("B1 freeze record drifted")
    if preregistration["repository_commit_under_test"] != B1_REPOSITORY_COMMIT_UNDER_TEST:
        raise SystemExit("B1 repository_commit_under_test drifted")

    assert_b1_is_held_out(preregistration, b0)
    schedule = build_b1_schedule(preregistration, preregistration_sha256=preregistration_sha256)
    attempts = cast(list[object], schedule["attempts"])
    if schedule["scheduled_attempt_count"] != B1_EXPECTED_ATTEMPTS or len(attempts) != B1_EXPECTED_ATTEMPTS:
        raise SystemExit("B1 frozen schedule is not exactly 28 primary attempts")

    method_ids: list[str] = []
    result_paths: set[str] = set()
    for raw_identity in attempts:
        identity = validate_b1_attempt_identity(raw_identity, preregistration)
        method_ids.append(cast(str, identity["method_id"]))
        relative = attempt_relative_path(identity)
        if relative.parts[0] != B1_FREEZE_COMMIT:
            raise SystemExit("B1 result path is not rooted at the recorded freeze commit")
        if any(part.lower() == "b0" for part in relative.parts):
            raise SystemExit("B1 result path crossed the frozen B0 evidence boundary")
        rendered = relative.as_posix()
        if rendered in result_paths:
            raise SystemExit(f"duplicate B1 result path: {rendered}")
        result_paths.add(rendered)

    if set(method_ids) != set(B1_SCORED_METHOD_IDS):
        raise SystemExit("B1 schedule does not cover both frozen scored methods")

    print(
        "B1-S0 checkpoint: "
        f"freeze={B1_FREEZE_COMMIT} "
        f"repository_commit_under_test={B1_REPOSITORY_COMMIT_UNDER_TEST} "
        f"attempts={len(attempts)} held_out=yes provider_invoked=no"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
