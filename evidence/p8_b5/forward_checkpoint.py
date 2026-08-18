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
    if type(lane) is not dict:
        raise SystemExit("P8-B5 forward checkpoint core lane malformed")
    children = lane.get("child_sequences")
    if type(children) is not dict:
        raise SystemExit("P8-B5 forward checkpoint child sequence malformed")
    p8 = cast(dict[str, object], children).get("P8")
    if type(p8) is not list or "P8-B5" not in cast(list[object], p8):
        raise SystemExit("P8-B5 forward checkpoint requires declared P8-B5 history")
    names = cast(list[str], p8)
    if "P8-B6" not in names or names.index("P8-B5") >= names.index("P8-B6"):
        raise SystemExit("P8-B5/B6 declared ordering drifted")

    # Preserve every legacy B5 package/authority check after the live lane has
    # advanced beyond P8 by feeding it a compatibility snapshot of the exact
    # historical P8-B5 position. Evidence files themselves are not rewritten.
    normalized = dict(lane)
    normalized["current"] = "P8"
    normalized["current_child"] = "P8-B5"
    normalized["active_issue"] = 92
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
