from __future__ import annotations

from typing import Mapping


P7_ISSUE = 71
B1_ISSUE = 79


def _string_list(value: object, label: str) -> list[str]:
    if type(value) is not list or not all(type(item) is str for item in value):
        raise SystemExit(f"{label} must be a list of strings")
    return value


def validate_p7_completion_lane(
    lane: Mapping[str, object],
    *,
    checkpoint_child: str,
) -> None:
    sequence = _string_list(lane.get("sequence"), "core lane sequence")
    current = lane.get("current")
    if type(current) is not str or current not in sequence:
        raise SystemExit("core lane current phase must be declared in sequence")
    if "P7" not in sequence or "B1" not in sequence:
        raise SystemExit("core lane must retain both P7 and B1 phases")

    child_sequences = lane.get("child_sequences")
    if type(child_sequences) is not dict:
        raise SystemExit("core lane child_sequences must be an object")
    p7_children = _string_list(child_sequences.get("P7"), "P7 child sequence")
    if checkpoint_child not in p7_children:
        raise SystemExit(f"unknown P7 checkpoint child: {checkpoint_child}")

    current_index = sequence.index(current)
    p7_index = sequence.index("P7")
    b1_index = sequence.index("B1")
    if current_index < p7_index:
        raise SystemExit("P7 completion evidence cannot be validated before the P7 phase")

    if current == "P7":
        current_child = lane.get("current_child")
        if type(current_child) is not str or current_child not in p7_children:
            raise SystemExit("active P7 child must be declared in the P7 child sequence")
        if p7_children.index(current_child) < p7_children.index(checkpoint_child):
            raise SystemExit(
                f"{checkpoint_child} checkpoint cannot validate before its child is active"
            )
        if lane.get("active_issue") != P7_ISSUE:
            raise SystemExit(f"active P7 work must remain on issue #{P7_ISSUE}")
        return

    if current_index < b1_index:
        raise SystemExit("completed P7 evidence may only hand off to B1 or a later phase")

    if current == "B1":
        b1_children = _string_list(child_sequences.get("B1"), "B1 child sequence")
        current_child = lane.get("current_child")
        if type(current_child) is not str or current_child not in b1_children:
            raise SystemExit("active B1 child must be declared in the B1 child sequence")
        if lane.get("active_issue") != B1_ISSUE:
            raise SystemExit(f"active B1 work must remain on issue #{B1_ISSUE}")
