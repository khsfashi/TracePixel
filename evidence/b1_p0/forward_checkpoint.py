from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from evidence.b1_p0 import checkpoint as legacy

ROOT = Path(__file__).resolve().parents[2]
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def run() -> dict[str, object]:
    live = json.loads(CORE_LANE.read_text(encoding="utf-8"))
    if type(live) is not dict:
        raise legacy.CheckpointError("live core lane malformed")
    sequence = cast(dict[str, object], live).get("sequence")
    children = cast(dict[str, object], live).get("child_sequences")
    if type(sequence) is not list or type(children) is not dict:
        raise legacy.CheckpointError("live core lane history malformed")
    ordered = cast(list[object], sequence)
    if "P8" not in ordered:
        raise legacy.CheckpointError("B1-P0 forward checkpoint requires declared P8 handoff history")
    p8 = cast(dict[str, object], children).get("P8")
    if type(p8) is not list or "P8-B6" not in cast(list[object], p8):
        raise legacy.CheckpointError("B1-P0 forward checkpoint requires completed P8 child history")

    historical = dict(cast(dict[str, object], live))
    historical["current"] = "P8"
    historical["current_child"] = "P8-B6"
    historical["active_issue"] = 92

    with TemporaryDirectory() as temporary:
        lane_path = Path(temporary) / "tracepixel.core-lane.json"
        lane_path.write_text(json.dumps(historical), encoding="utf-8")
        original = legacy.CORE_LANE
        try:
            legacy.CORE_LANE = lane_path
            return legacy.run()
        finally:
            legacy.CORE_LANE = original


def main() -> int:
    print(json.dumps(run(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
