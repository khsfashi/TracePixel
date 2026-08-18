from __future__ import annotations

import pytest

from evidence.g8_h5 import raw_matched_baseline as raw


def test_raw_baseline_is_one_call_and_not_humanoid_contract_bound() -> None:
    assert raw.DIRECT_RUN_ID == 32118899233
    assert raw.MAX_PROVIDER_CALLS == 1
    assert raw.MODEL == "gpt-5.6-sol"
    assert raw.REASONING_EFFORT == "low"
    assert "BOUND_HUMANOID_CONTEXT" not in raw.RAW_TASK
    assert "tracepixel.humanoid" not in raw.RAW_TASK
    assert "Return raw raster pixel data only" in raw.RAW_TASK
    assert raw._OUTPUT_SCHEMA["properties"]["schema"]["const"] == raw.SCHEMA


def test_raw_response_lowers_directly_to_canvas_without_pixelprogram() -> None:
    response = {
        "schema": raw.SCHEMA,
        "canvas": {"width": 32, "height": 32},
        "pixels": [
            [10, 10, 1, 2, 3, 255],
            [11, 10, 4, 5, 6, 255],
        ],
    }
    canvas, edits = raw._canvas_from_response(response)
    assert edits == 2
    assert canvas.get_pixel(10, 10) == (1, 2, 3, 255)
    assert canvas.get_pixel(11, 10) == (4, 5, 6, 255)


def test_raw_response_fails_closed_on_duplicate_coordinate() -> None:
    response = {
        "schema": raw.SCHEMA,
        "canvas": {"width": 32, "height": 32},
        "pixels": [
            [10, 10, 1, 2, 3, 255],
            [10, 10, 4, 5, 6, 255],
        ],
    }
    with pytest.raises(RuntimeError, match="duplicate pixel"):
        raw._canvas_from_response(response)


def test_usage_parser_reads_last_completed_turn() -> None:
    stdout = "\n".join(
        [
            '{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":3}}',
            '{"type":"turn.completed","usage":{"input_tokens":20,"output_tokens":5}}',
        ]
    )
    assert raw._usage_from_jsonl(stdout) == (20, 5)
