from __future__ import annotations

import contextlib
import io
import json
import unittest

from tracepixel import __version__
from tracepixel.cli import main


class CliTests(unittest.TestCase):
    def test_doctor_is_compact_valid_json(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["doctor"])

        self.assertEqual(result, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["schema"], "tracepixel.doctor.v1")
        self.assertEqual(payload["tracepixel_version"], __version__)
        self.assertTrue(payload["capabilities"]["core_package"])
        self.assertFalse(payload["capabilities"]["live_provider_required"])
        self.assertFalse(payload["capabilities"]["gpu_required"])


if __name__ == "__main__":
    unittest.main()
