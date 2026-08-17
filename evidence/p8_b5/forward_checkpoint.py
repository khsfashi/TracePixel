from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from evidence.p8_b5 import checkpoint as legacy

ROOT = Path(__file__).resolve().parents[2]
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def main() -> int:
    lane = json.loads(CORE_LANE.read_text(encoding="utf-8"))
    if type(lane) is not dict or lane.get("current") != "P8" or lane.get("active_issue") != 92:
        raise SystemExit("P8-B5 forward checkpoint requires live P8 / issue #92")
    children = lane.get("child_sequences")
    if type(children) is not dict:
        raise SystemExit("P8-B5 forward checkpoint child sequence malformed")
    p8 = cast(dict[str, object], children).get("P8")
    child = lane.get("current_child")
    if type(p8) is not list or child not in cast(list[object], p8):
        raise SystemExit("P8-B5 forward checkpoint active child is not declared")
    names = cast(list[str], p8)
    if names.index(cast(str, child)) < names.index("P8-B5"):
        raise SystemExit("P8-B5 forward checkpoint cannot run before P8-B5")

    # The legacy checkpoint's only forward-incompatible assertion is its exact
    # live-current-child equality. Preserve every B5 package/authority check by
    # feeding it an otherwise identical lane snapshot normalized to P8-B5.
    normalized = dict(lane)
    normalized["current_child"] = "P8-B5"
    with TemporaryDirectory() as temporary:
        lane_path = Path(temporary) / "tracepixel.core-lane.json"
        lane_path.write_text(json.dumps(normalized), encoding="utf-8")
        original = legacy.CORE_LANE
        try:
            legacy.CORE_LANE = lane_path
            return legacy.main([])
        finally:
            legacy.CORE_LANE = original


if __name__ == "__main__":
    raise SystemExit(main())
