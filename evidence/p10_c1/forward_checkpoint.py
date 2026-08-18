from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from evidence.p10_c1 import checkpoint as legacy

ROOT = Path(__file__).resolve().parents[2]
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"


def main() -> int:
    live = json.loads(CORE_LANE.read_text(encoding="utf-8"))
    if type(live) is not dict:
        raise SystemExit("P10-C1 forward checkpoint failed: live core lane malformed")
    children = cast(dict[str, object], live).get("child_sequences")
    if type(children) is not dict:
        raise SystemExit("P10-C1 forward checkpoint failed: child sequence missing")
    p10 = cast(dict[str, object], children).get("P10")
    if type(p10) is not list or "P10-C1" not in cast(list[object], p10):
        raise SystemExit("P10-C1 forward checkpoint failed: P10-C1 history missing")

    historical = dict(cast(dict[str, object], live))
    historical["current"] = "P10"
    historical["current_child"] = "P10-C1"
    historical["active_issue"] = 109

    with TemporaryDirectory() as temporary:
        lane_path = Path(temporary) / "tracepixel.core-lane.json"
        lane_path.write_text(json.dumps(historical), encoding="utf-8")
        original = legacy.CORE_LANE
        try:
            legacy.CORE_LANE = lane_path
            return legacy.main()
        finally:
            legacy.CORE_LANE = original


if __name__ == "__main__":
    raise SystemExit(main())
