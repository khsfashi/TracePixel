from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, cast

ROOT = Path(__file__).resolve().parents[2]
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"

_MODULES = (
    "evidence.p8_x0.checkpoint",
    "evidence.p8_r0.checkpoint",
    "evidence.p8_b0.checkpoint",
    "evidence.p8_b1.checkpoint",
    "evidence.p8_c0.checkpoint",
    "evidence.p8_b2.checkpoint",
    "evidence.p8_b3.checkpoint",
    "evidence.p8_b4.checkpoint",
    "evidence.p8_b5.forward_checkpoint",
    "evidence.p8_b6.checkpoint",
)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _invoke(main_func: Callable[..., object]) -> object:
    parameters = inspect.signature(main_func).parameters
    if not parameters:
        return main_func()
    if len(parameters) == 1:
        return main_func([])
    raise SystemExit(f"unsupported frozen checkpoint main signature: {inspect.signature(main_func)}")


def main() -> int:
    live = _json(CORE_LANE)
    sequence = live.get("sequence")
    children = live.get("child_sequences")
    if type(sequence) is not list or type(children) is not dict:
        raise SystemExit("P8 history checkpoint core lane malformed")
    ordered = cast(list[object], sequence)
    if "P8" not in ordered or "P10" not in ordered or ordered.index("P8") >= ordered.index("P10"):
        raise SystemExit("P8 history checkpoint requires the live lane to have advanced from P8 to P10")
    p8 = cast(dict[str, object], children).get("P8")
    if type(p8) is not list or not p8 or cast(list[object], p8)[-1] != "P8-B6":
        raise SystemExit("frozen P8 child history must terminate at P8-B6")

    # Frozen checkpoints are allowed to depend on the live-lane position they
    # originally closed. Recreate that historical lane position only for their
    # CORE_LANE read; all retained evidence, fixtures, source code and authority
    # checks remain the real repository files and are executed unchanged.
    historical = dict(live)
    historical["current"] = "P8"
    historical["current_child"] = "P8-B6"
    historical["active_issue"] = 92

    with TemporaryDirectory() as temporary:
        lane_path = Path(temporary) / "tracepixel.core-lane.json"
        lane_path.write_text(json.dumps(historical), encoding="utf-8")

        for module_name in _MODULES:
            module = importlib.import_module(module_name)
            main_func = getattr(module, "main", None)
            if not callable(main_func):
                raise SystemExit(f"frozen checkpoint has no callable main: {module_name}")

            had_core_lane = hasattr(module, "CORE_LANE")
            original = getattr(module, "CORE_LANE", None)
            if had_core_lane:
                setattr(module, "CORE_LANE", lane_path)
            try:
                result = _invoke(cast(Callable[..., object], main_func))
            finally:
                if had_core_lane:
                    setattr(module, "CORE_LANE", original)

            if result not in (None, 0):
                raise SystemExit(f"frozen checkpoint returned non-zero: {module_name}: {result!r}")
            print(json.dumps({"p8_history_checkpoint": module_name, "status": "pass"}, sort_keys=True))

    print(json.dumps({
        "schema": "tracepixel.p8-history-checkpoint.v1",
        "status": "pass",
        "frozen_checkpoint_count": len(_MODULES),
        "historical_child": "P8-B6",
        "live_child": live.get("current_child"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
