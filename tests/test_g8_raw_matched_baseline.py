from __future__ import annotations

import unittest

from evidence.g8_h5 import raw_matched_baseline as raw


class G8RawMatchedBaselineTests(unittest.TestCase):
    def test_raw_baseline_is_one_call_and_not_humanoid_contract_bound(self) -> None:
        self.assertEqual(raw.DIRECT_RUN_ID, 32118899233)
        self.assertEqual(raw.MAX_PROVIDER_CALLS, 1)
        self.assertEqual(raw.MODEL, "gpt-5.6-sol")
        self.assertEqual(raw.REASONING_EFFORT, "low")
        self.assertNotIn("BOUND_HUMANOID_CONTEXT", raw.RAW_TASK)
        self.assertNotIn("tracepixel.humanoid", raw.RAW_TASK)
        self.assertIn("Return raw raster pixel data only", raw.RAW_TASK)
        self.assertEqual(raw._OUTPUT_SCHEMA["properties"]["schema"]["const"], raw.SCHEMA)

    def test_raw_response_lowers_directly_to_canvas_without_pixelprogram(self) -> None:
        response = {
            "schema": raw.SCHEMA,
            "canvas": {"width": 32, "height": 32},
            "pixels": [
                [10, 10, 1, 2, 3, 255],
                [11, 10, 4, 5, 6, 255],
            ],
        }
        canvas, edits = raw._canvas_from_response(response)
        self.assertEqual(edits, 2)
        self.assertEqual(canvas.get_pixel(10, 10), (1, 2, 3, 255))
        self.assertEqual(canvas.get_pixel(11, 10), (4, 5, 6, 255))

    def test_raw_response_fails_closed_on_duplicate_coordinate(self) -> None:
        response = {
            "schema": raw.SCHEMA,
            "canvas": {"width": 32, "height": 32},
            "pixels": [
                [10, 10, 1, 2, 3, 255],
                [10, 10, 4, 5, 6, 255],
            ],
        }
        with self.assertRaisesRegex(RuntimeError, "duplicate pixel"):
            raw._canvas_from_response(response)

    def test_usage_parser_reads_last_completed_turn(self) -> None:
        stdout = "\n".join(
            [
                '{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":3}}',
                '{"type":"turn.completed","usage":{"input_tokens":20,"output_tokens":5}}',
            ]
        )
        self.assertEqual(raw._usage_from_jsonl(stdout), (20, 5))


if __name__ == "__main__":
    unittest.main()
