from __future__ import annotations

from pathlib import Path
from typing import cast

from tracepixel.benchmark import (
    B0CodexCall,
    B0_RAW_METHOD_ID,
    B0_TRACEPIXEL_METHOD_ID,
    b0_feedback_from_qa,
    build_b0_schedule,
    load_b0_preregistration,
    run_b0_attempt,
    score_b0_canvas,
    validate_b0_scoring_contract,
)
from tracepixel.model import execute_pixel_program

PREREGISTRATION = Path(__file__).parents[1] / "b0" / "preregistration.v1.json"


def _diamond_program() -> dict[str, object]:
    pixels: list[list[int]] = []
    rows = {
        4: (7, 8),
        5: (6, 7, 8, 9),
        6: (5, 6, 7, 8, 9, 10),
        7: tuple(range(4, 12)),
        8: tuple(range(4, 12)),
        9: (5, 6, 7, 8, 9, 10),
        10: (6, 7, 8, 9),
        11: (7, 8),
    }
    for y, xs in rows.items():
        for x in xs:
            pixels.append([x, y, 0, 220, 255, 255])
    return {
        "schema": "tracepixel.pixel-program.v1",
        "canvas": {"width": 16, "height": 16},
        "operations": [{"op": "set_pixels", "pixels": pixels}],
    }


class _RecordedExecutor:
    def __init__(self, program: dict[str, object]) -> None:
        self.program = program
        self.requests: list[dict[str, object]] = []

    def invoke(self, request, *, call_index: int) -> B0CodexCall:
        self.requests.append(request)
        if request["attempt"]["method_id"] == B0_TRACEPIXEL_METHOD_ID:
            output: object = {
                "schema": "tracepixel.agent-provider-proposal.v1",
                "kind": "pixel_program",
                "payload": self.program,
            }
        else:
            output = self.program
        return B0CodexCall(
            status="response",
            output=output,
            raw_output="{}",
            input_tokens=100 + call_index,
            output_tokens=50,
            tool_calls=0,
            wall_time_ms=1,
            returncode=0,
            error_code=None,
        )


def main() -> None:
    preregistration, digest = load_b0_preregistration(PREREGISTRATION)
    validate_b0_scoring_contract(preregistration)
    schedule = build_b0_schedule(preregistration, preregistration_sha256=digest)
    assert schedule["scheduled_attempt_count"] == 28

    program = _diamond_program()
    qa = score_b0_canvas(preregistration, "B0-T0-01", execute_pixel_program(program))
    assert qa["all_rules_pass"] is True
    feedback = b0_feedback_from_qa(qa)
    assert feedback["available"] is True
    assert feedback["findings"] == []

    identities = cast(list[dict[str, object]], schedule["attempts"])
    for method_id in (B0_TRACEPIXEL_METHOD_ID, B0_RAW_METHOD_ID):
        identity = next(item for item in identities if item["task_id"] == "B0-T0-01" and item["method_id"] == method_id)
        executor = _RecordedExecutor(program)
        execution = run_b0_attempt(
            preregistration,
            identity=cast(object, identity),
            executor=executor,
            runner_commit="0" * 40,
        )
        assert execution.result["completion"] is True
        assert execution.result["structural"]["all_rules_pass"] is True
        assert execution.result["failure_category"] is None
        assert set(("final.rgba", "final.png", "preview-8x.png")) <= set(execution.payloads)
        assert len(executor.requests) == 1
        request_text = str(executor.requests[0])
        assert "hidden_structural_constraints" not in request_text

    print("B0-S0 provider-free scored cohort checkpoint: PASS")


if __name__ == "__main__":
    main()
