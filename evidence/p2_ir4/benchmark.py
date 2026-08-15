from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Sequence

from tracepixel.model import (
    PIXEL_PROGRAM_SCHEMA_V1,
    PixelProgramSerializationError,
    PixelProgramValidationError,
    deserialize_pixel_program,
    execute_pixel_program,
    serialize_pixel_program,
    validate_pixel_program,
)
from tracepixel.raster import Canvas

EVIDENCE_SCHEMA = "tracepixel.p2-ir4-engineering-evidence.v1"
TOKEN_PROXY = "ceil(utf8_bytes/4) per serialized form"
PUBLIC_OPERATION_VOCABULARY = ("set_pixels",)

_FIXTURES = (
    {
        "id": "potion-16",
        "palette": {
            ".": (0, 0, 0, 0),
            "K": (35, 28, 45, 255),
            "C": (164, 105, 57, 255),
            "H": (225, 166, 88, 255),
            "B": (132, 190, 230, 255),
            "G": (76, 122, 176, 255),
            "R": (192, 48, 68, 255),
            "L": (246, 104, 104, 255),
        },
        "rows": (
            "................",
            "......CCCC......",
            ".....CHHHC......",
            ".....KKKKK......",
            "......KKK.......",
            ".....KBBBK......",
            "....KBGGGBK.....",
            "...KBGGGGGBK....",
            "...KBBRRRBBK....",
            "..KBRRRRRRBK....",
            "..KRRRLLRRRK....",
            "..KRRLLLLRRK....",
            "...KRRRRRRK.....",
            "....KRRRRK......",
            ".....KKKK.......",
            "................",
        ),
    },
    {
        "id": "gem-16",
        "palette": {
            ".": (0, 0, 0, 0),
            "K": (31, 33, 52, 255),
            "B": (68, 146, 210, 255),
            "H": (151, 226, 255, 255),
        },
        "rows": (
            "................",
            ".......KK.......",
            "......KBBK......",
            ".....KBBBBK.....",
            "....KBBHHBBK....",
            "...KBBHHHHBBK...",
            "..KBBBHHHHBBBK..",
            ".KBBBBBBBBBBBBK.",
            "..KBBBBBBBBBBK..",
            "...KBBBBBBBBK...",
            "....KBBBBBBK....",
            ".....KBBBBK.....",
            "......KBBK......",
            ".......KK.......",
            "................",
            "................",
        ),
    },
    {
        "id": "key-16",
        "palette": {
            ".": (0, 0, 0, 0),
            "K": (48, 39, 30, 255),
            "H": (225, 174, 64, 255),
            "L": (255, 221, 117, 255),
        },
        "rows": (
            "................",
            "..........KK....",
            ".........KLLK...",
            "........KLHHK...",
            "........KH.HK...",
            ".........KHHK...",
            "..........KK....",
            "...KKKKKKKKK....",
            "..KHHHHHHHHK....",
            "...KKKKKKKKK....",
            "....KK..KK......",
            "....KK..KK......",
            "................",
            "................",
            "................",
            "................",
        ),
    },
)


def _compact_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _token_proxy(payload: bytes) -> int:
    return (len(payload) + 3) // 4


def _fixture_edits(fixture: dict[str, object]) -> list[list[int]]:
    rows = fixture["rows"]
    palette = fixture["palette"]
    if not isinstance(rows, tuple) or not isinstance(palette, dict):
        raise AssertionError("fixture definition shape drifted")
    if not rows:
        raise AssertionError("fixture rows must not be empty")

    width = len(rows[0])
    edits: list[list[int]] = []
    for y, row in enumerate(rows):
        if not isinstance(row, str) or len(row) != width:
            raise AssertionError("fixture row width drifted")
        for x, token in enumerate(row):
            if token == ".":
                continue
            color = palette[token]
            if not isinstance(color, tuple) or len(color) != 4:
                raise AssertionError("fixture palette entry drifted")
            edits.append([x, y, color[0], color[1], color[2], color[3]])
    return edits


def _fixture_program(fixture: dict[str, object]) -> dict[str, object]:
    rows = fixture["rows"]
    if not isinstance(rows, tuple):
        raise AssertionError("fixture rows shape drifted")
    return {
        "schema": PIXEL_PROGRAM_SCHEMA_V1,
        "canvas": {"width": len(rows[0]), "height": len(rows)},
        "operations": [{"op": "set_pixels", "pixels": _fixture_edits(fixture)}],
    }


def _raw_primitive_document(
    width: int,
    height: int,
    edits: list[list[int]],
) -> dict[str, object]:
    return {
        "canvas": [width, height],
        "calls": [["set_pixel", *edit] for edit in edits],
    }


def _raw_primitive_replay(width: int, height: int, edits: list[list[int]]) -> Canvas:
    canvas = Canvas(width, height)
    for x, y, red, green, blue, alpha in edits:
        canvas.set_pixel(x, y, (red, green, blue, alpha))
    return canvas


def build_fixture_evidence(fixture: dict[str, object]) -> dict[str, object]:
    fixture_id = fixture["id"]
    program = _fixture_program(fixture)
    canvas_doc = program["canvas"]
    operations = program["operations"]
    if not isinstance(fixture_id, str):
        raise AssertionError("fixture id drifted")
    if not isinstance(canvas_doc, dict) or not isinstance(operations, list):
        raise AssertionError("program shape drifted")

    width = canvas_doc["width"]
    height = canvas_doc["height"]
    if type(width) is not int or type(height) is not int:
        raise AssertionError("fixture dimensions drifted")

    edits = operations[0]["pixels"]
    if not isinstance(edits, list):
        raise AssertionError("fixture edits drifted")

    canonical = serialize_pixel_program(program)
    raw_primitive = _compact_json_bytes(
        _raw_primitive_document(width, height, edits)
    )
    bare_edits = _compact_json_bytes(edits)

    ir_canvas = execute_pixel_program(program)
    raw_canvas = _raw_primitive_replay(width, height, edits)
    replay_equal = ir_canvas.rgba_bytes() == raw_canvas.rgba_bytes()

    return {
        "fixture": fixture_id,
        "width": width,
        "height": height,
        "edit_count": len(edits),
        "public_operation_count": len(operations),
        "raw_primitive_call_count": len(edits),
        "canonical_pixel_program_bytes": len(canonical),
        "raw_primitive_call_stream_bytes": len(raw_primitive),
        "bare_edit_array_bytes": len(bare_edits),
        "canonical_token_proxy": _token_proxy(canonical),
        "raw_primitive_token_proxy": _token_proxy(raw_primitive),
        "bare_edit_array_token_proxy": _token_proxy(bare_edits),
        "canonical_vs_raw_primitive_saved_bytes": len(raw_primitive) - len(canonical),
        "canonical_envelope_over_bare_edits_bytes": len(canonical) - len(bare_edits),
        "exact_replay_equal": replay_equal,
    }


def _base_invalidity_program() -> dict[str, object]:
    return {
        "schema": PIXEL_PROGRAM_SCHEMA_V1,
        "canvas": {"width": 1, "height": 1},
        "operations": [
            {
                "op": "set_pixels",
                "pixels": [[0, 0, 1, 2, 3, 255]],
            }
        ],
    }


def _validation_cases() -> tuple[tuple[str, object, str, str], ...]:
    missing_schema = _base_invalidity_program()
    del missing_schema["schema"]

    unsupported_schema = _base_invalidity_program()
    unsupported_schema["schema"] = "tracepixel.pixel-program.v2"

    invalid_canvas = _base_invalidity_program()
    invalid_canvas["canvas"]["width"] = True  # type: ignore[index]

    unsupported_operation = _base_invalidity_program()
    unsupported_operation["operations"][0]["op"] = "set_pixel"  # type: ignore[index]

    invalid_edit = _base_invalidity_program()
    invalid_edit["operations"][0]["pixels"][0] = [0, 0, 1]  # type: ignore[index]

    invalid_coordinate = _base_invalidity_program()
    invalid_coordinate["operations"][0]["pixels"][0][0] = 1  # type: ignore[index]

    invalid_color = _base_invalidity_program()
    invalid_color["operations"][0]["pixels"][0][2] = 256  # type: ignore[index]

    return (
        ("root_type", [], "invalid_type", "$"),
        ("missing_schema", missing_schema, "invalid_fields", "$"),
        ("unsupported_schema", unsupported_schema, "unsupported_schema", "$.schema"),
        ("invalid_canvas", invalid_canvas, "invalid_canvas", "$.canvas"),
        (
            "unsupported_operation",
            unsupported_operation,
            "unsupported_operation",
            "$.operations[0].op",
        ),
        (
            "invalid_edit",
            invalid_edit,
            "invalid_edit",
            "$.operations[0].pixels[0]",
        ),
        (
            "invalid_coordinate",
            invalid_coordinate,
            "invalid_coordinate",
            "$.operations[0].pixels[0]",
        ),
        (
            "invalid_color",
            invalid_color,
            "invalid_color",
            "$.operations[0].pixels[0]",
        ),
    )


def build_invalidity_evidence() -> dict[str, object]:
    validation_results: list[dict[str, object]] = []
    for name, program, expected_code, expected_path in _validation_cases():
        observed_code: str | None = None
        observed_path: str | None = None
        rejected = False
        try:
            validate_pixel_program(program)
        except PixelProgramValidationError as exc:
            rejected = True
            observed_code = exc.code
            observed_path = exc.path

        validation_results.append(
            {
                "case": name,
                "expected_code": expected_code,
                "expected_path": expected_path,
                "rejected": rejected,
                "observed_code": observed_code,
                "observed_path": observed_path,
                "expected_match": (
                    rejected
                    and observed_code == expected_code
                    and observed_path == expected_path
                ),
            }
        )

    wire_results: list[dict[str, object]] = []
    for name, payload, expected_code in (
        ("wire_non_bytes", "{}", "invalid_type"),
        ("wire_malformed_json", b"{", "invalid_json"),
    ):
        observed_code: str | None = None
        rejected = False
        try:
            deserialize_pixel_program(payload)
        except PixelProgramSerializationError as exc:
            rejected = True
            observed_code = exc.code

        wire_results.append(
            {
                "case": name,
                "expected_code": expected_code,
                "rejected": rejected,
                "observed_code": observed_code,
                "expected_match": rejected and observed_code == expected_code,
            }
        )

    return {
        "validation_cases": validation_results,
        "wire_cases": wire_results,
        "all_expected_failures_observed": all(
            bool(case["expected_match"])
            for case in (*validation_results, *wire_results)
        ),
    }


def build_evidence() -> dict[str, object]:
    fixture_evidence = [build_fixture_evidence(fixture) for fixture in _FIXTURES]
    totals = {
        "fixture_count": len(fixture_evidence),
        "edit_count": sum(int(case["edit_count"]) for case in fixture_evidence),
        "public_operation_count": sum(
            int(case["public_operation_count"]) for case in fixture_evidence
        ),
        "raw_primitive_call_count": sum(
            int(case["raw_primitive_call_count"]) for case in fixture_evidence
        ),
        "canonical_pixel_program_bytes": sum(
            int(case["canonical_pixel_program_bytes"]) for case in fixture_evidence
        ),
        "raw_primitive_call_stream_bytes": sum(
            int(case["raw_primitive_call_stream_bytes"]) for case in fixture_evidence
        ),
        "bare_edit_array_bytes": sum(
            int(case["bare_edit_array_bytes"]) for case in fixture_evidence
        ),
        "canonical_token_proxy": sum(
            int(case["canonical_token_proxy"]) for case in fixture_evidence
        ),
        "raw_primitive_token_proxy": sum(
            int(case["raw_primitive_token_proxy"]) for case in fixture_evidence
        ),
        "bare_edit_array_token_proxy": sum(
            int(case["bare_edit_array_token_proxy"]) for case in fixture_evidence
        ),
    }
    totals["canonical_vs_raw_primitive_saved_bytes"] = (
        totals["raw_primitive_call_stream_bytes"]
        - totals["canonical_pixel_program_bytes"]
    )
    totals["canonical_envelope_over_bare_edits_bytes"] = (
        totals["canonical_pixel_program_bytes"] - totals["bare_edit_array_bytes"]
    )

    invalidity = build_invalidity_evidence()
    return {
        "schema": EVIDENCE_SCHEMA,
        "scope": "engineering-checkpoint-not-scored-product-claim",
        "token_proxy": {
            "definition": TOKEN_PROXY,
            "actual_model_tokens": False,
        },
        "baselines": {
            "raw_primitive_call_stream": (
                "compact JSON engineering baseline with one set_pixel call per edit"
            ),
            "bare_edit_array": (
                "compact JSON payload lower bound without schema/canvas/operation context"
            ),
        },
        "public_operation_vocabulary": list(PUBLIC_OPERATION_VOCABULARY),
        "vocabulary_decision": {
            "decision": "retain-single-set_pixels-operation-for-pixel-program-v1",
            "reason": (
                "the fixed visible fixture set replays exactly with one public operation "
                "per fixture; no overlapping convenience operation has measured evidence "
                "that justifies increasing the v1 concept budget"
            ),
        },
        "fixtures": fixture_evidence,
        "totals": totals,
        "invalidity": invalidity,
        "all_fixture_replays_equal": all(
            bool(case["exact_replay_equal"]) for case in fixture_evidence
        ),
    }


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect TracePixel P2-IR4 IR compactness/replay/invalidity evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON output path; stdout is always emitted",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_evidence()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
