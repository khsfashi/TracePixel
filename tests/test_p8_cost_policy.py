from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "config" / "tracepixel.core-lane.json"
COST_REPORT = ROOT / "evidence" / "p8_c0" / "report.v1.json"


class P8CostPolicyTests(unittest.TestCase):
    def _lane(self) -> dict[str, object]:
        value = json.loads(LANE.read_text(encoding="utf-8"))
        self.assertIs(type(value), dict)
        return value

    def test_cost_gate_is_mandatory_before_breadth(self) -> None:
        lane = self._lane()
        child_sequences = lane["child_sequences"]
        self.assertIs(type(child_sequences), dict)
        p8 = child_sequences["P8"]
        self.assertIs(type(p8), list)
        self.assertLess(p8.index("P8-B1"), p8.index("P8-C0"))
        self.assertLess(p8.index("P8-C0"), p8.index("P8-B2"))

        checkpoints = lane["engineering_checkpoints"]
        self.assertIs(type(checkpoints), dict)
        self.assertIn("P8-C0", checkpoints)

    def test_breadth_cannot_advance_without_passed_cost_report(self) -> None:
        lane = self._lane()
        sequence = lane["sequence"]
        self.assertIs(type(sequence), list)
        current = lane["current"]
        self.assertIs(type(current), str)

        requires_report = sequence.index(current) > sequence.index("P8")
        if current == "P8":
            child_sequences = lane["child_sequences"]
            self.assertIs(type(child_sequences), dict)
            p8 = child_sequences["P8"]
            self.assertIs(type(p8), list)
            current_child = lane["current_child"]
            self.assertIs(type(current_child), str)
            requires_report = p8.index(current_child) >= p8.index("P8-B2")

        if not requires_report:
            return

        self.assertTrue(
            COST_REPORT.is_file(),
            "P8-B2+ is blocked until evidence/p8_c0/report.v1.json exists",
        )
        report = json.loads(COST_REPORT.read_text(encoding="utf-8"))
        self.assertIs(type(report), dict)
        self.assertEqual(report.get("schema"), "tracepixel.p8-cost-scaling-report.v1")
        self.assertEqual(report.get("status"), "passed")
        self.assertTrue(report.get("batch_orchestration_no_hidden_multiplier"))


if __name__ == "__main__":
    unittest.main()
