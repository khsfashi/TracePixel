from __future__ import annotations

import unittest

from evidence.b1_p0.forward_checkpoint import run


class B1P0PostmortemTests(unittest.TestCase):
    def test_frozen_postmortem_rederives_b1_evidence_and_handoff(self) -> None:
        result = run()
        self.assertEqual(result["schema"], "tracepixel.b1-p0-checkpoint.v1")
        self.assertEqual(result["scheduled_attempts"], 28)
        self.assertEqual(result["retained_attempts"], 28)
        self.assertEqual(result["owner_ratings"], 28)
        self.assertEqual(result["tracepixel_human_rejections"], 0)
        self.assertEqual(result["raw_human_rejections"], 1)
        self.assertEqual(result["tracepixel_repair_cycles_mean"], 0)
        self.assertEqual(result["next"], "P8-X0")


if __name__ == "__main__":
    unittest.main()
