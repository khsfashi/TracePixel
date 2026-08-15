from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from evidence.p5_a4.checkpoint import (
    RECORDING_PATH,
    RecordedProviderFixtureError,
    load_recording,
    verify_checkpoint,
)


class P5A4RecordedProviderCiTests(unittest.TestCase):
    def test_recorded_checkpoint_replays_deterministically(self) -> None:
        summary = verify_checkpoint()

        self.assertEqual(summary["record_count"], 2)
        self.assertEqual(summary["request_count"], 2)
        self.assertEqual(summary["status"], "finished")
        telemetry = summary["telemetry"]
        self.assertEqual(telemetry["input_tokens"], 220)
        self.assertEqual(telemetry["output_tokens"], 45)
        self.assertEqual(telemetry["tool_calls"], 2)
        self.assertEqual(telemetry["revisions"], 2)
        self.assertEqual(telemetry["changed_pixels"], 1)
        self.assertEqual(telemetry["api_cost_usd_micros"], 110)
        self.assertNotIn("wall_time_ns", telemetry)

    def test_recording_contract_rejects_extra_fields(self) -> None:
        fixture = json.loads(RECORDING_PATH.read_text(encoding="utf-8"))
        broken = copy.deepcopy(fixture)
        broken["unexpected"] = True

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recording.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaises(RecordedProviderFixtureError):
                load_recording(path)

    def test_recording_contract_rejects_invalid_usage(self) -> None:
        fixture = json.loads(RECORDING_PATH.read_text(encoding="utf-8"))
        broken = copy.deepcopy(fixture)
        broken["records"][0]["usage"]["input_tokens"] = True

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recording.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaises(RecordedProviderFixtureError):
                load_recording(path)


if __name__ == "__main__":
    unittest.main()
