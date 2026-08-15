from __future__ import annotations

import copy
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Sequence, cast

from tracepixel.agent import (
    AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1,
    AGENT_LOOP_BUDGET_SCHEMA_V1,
    AgentProviderUsage,
    run_bounded_edit_loop_with_telemetry,
)
from tracepixel.model import ART_INTENT_SCHEMA_V1
from tracepixel.qa import QA_POLICY_SCHEMA_V1, analyze_structural, evaluate_qa_policy
from tracepixel.raster import Canvas

RECORDING_SCHEMA_V1 = "tracepixel.p5-a4-recorded-provider.v1"
SUMMARY_SCHEMA_V1 = "tracepixel.p5-a4-recorded-ci-summary.v1"
RECORDING_PATH = Path(__file__).with_name("recording.json")
MAX_RECORDED_CALLS = 16

_ART_INTENT = {
    "schema": ART_INTENT_SCHEMA_V1,
    "asset_class": "test-icon",
    "canvas": {"width": 2, "height": 2},
    "composition": {
        "occupied_bounds": None,
        "facing": None,
        "symmetry": None,
        "light_direction": None,
        "palette_budget": None,
    },
}

_BUDGET = {
    "schema": AGENT_LOOP_BUDGET_SCHEMA_V1,
    "max_iterations": 4,
    "max_tool_calls": 4,
    "max_operations": 4,
    "max_pixel_edits": 8,
}

_EXPECTED_FINAL_RGBA = bytes((10, 20, 30, 255) + (0,) * 12)


class RecordedProviderFixtureError(ValueError):
    """Stable rejection for the synthetic P5-A4 recording fixture."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def _fail(path: str, message: str) -> None:
    raise RecordedProviderFixtureError(path, message)


def _require_exact_object(value: object, path: str, fields: frozenset[str]) -> dict[str, object]:
    if type(value) is not dict:
        _fail(path, "must be a JSON object")
    root = cast(dict[object, object], value)
    if not all(type(key) is str for key in root):
        _fail(path, "object keys must be strings")
    typed = cast(dict[str, object], root)
    actual = frozenset(typed)
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail(path, "; ".join(parts))
    return typed


def _optional_nonnegative_int(value: object, path: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or cast(int, value) < 0:
        _fail(path, "must be a non-negative integer or null")
    return cast(int, value)


def load_recording(path: Path = RECORDING_PATH) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecordedProviderFixtureError("$", f"cannot load recording: {exc}") from exc

    root = _require_exact_object(value, "$", frozenset(("schema", "records")))
    if root["schema"] != RECORDING_SCHEMA_V1:
        _fail("$.schema", f"expected {RECORDING_SCHEMA_V1!r}")

    records = root["records"]
    if type(records) is not list:
        _fail("$.records", "must be a JSON array")
    record_list = cast(list[object], records)
    if not 1 <= len(record_list) <= MAX_RECORDED_CALLS:
        _fail("$.records", f"must contain 1..{MAX_RECORDED_CALLS} recorded calls")

    for index, value in enumerate(record_list):
        record_path = f"$.records[{index}]"
        record = _require_exact_object(value, record_path, frozenset(("proposal", "usage")))
        if type(record["proposal"]) is not dict:
            _fail(f"{record_path}.proposal", "must be a JSON object")
        usage = _require_exact_object(
            record["usage"],
            f"{record_path}.usage",
            frozenset(("input_tokens", "output_tokens", "api_cost_usd_micros")),
        )
        for field in ("input_tokens", "output_tokens", "api_cost_usd_micros"):
            _optional_nonnegative_int(usage[field], f"{record_path}.usage.{field}")
    return root


class _NonEmptyQa:
    _policy = {
        "schema": QA_POLICY_SCHEMA_V1,
        "rules": [{"rule": "structural.non_empty", "severity": "error"}],
    }

    def evaluate(self, canvas: Canvas):
        return evaluate_qa_policy(
            self._policy,
            structural=analyze_structural(canvas),
        )


class _RecordedProvider:
    def __init__(self, records: list[object]) -> None:
        self._records = records
        self._index = 0
        self._last_usage: AgentProviderUsage | None = None
        self.requests: list[object] = []

    @property
    def remaining(self) -> int:
        return len(self._records) - self._index

    def propose(self, request):
        if self._index >= len(self._records):
            raise AssertionError("recorded provider was called after the fixture was exhausted")
        record = cast(dict[str, object], self._records[self._index])
        self._index += 1
        self.requests.append(copy.deepcopy(request))

        usage = cast(dict[str, object], record["usage"])
        self._last_usage = AgentProviderUsage(
            input_tokens=cast(int | None, usage["input_tokens"]),
            output_tokens=cast(int | None, usage["output_tokens"]),
            api_cost_usd_micros=cast(int | None, usage["api_cost_usd_micros"]),
        )
        return copy.deepcopy(record["proposal"])

    def last_usage(self) -> AgentProviderUsage | None:
        return self._last_usage


def _run_once(path: Path) -> dict[str, Any]:
    recording = load_recording(path)
    records = cast(list[object], recording["records"])
    provider = _RecordedProvider(records)
    canvas = Canvas(2, 2)

    result = run_bounded_edit_loop_with_telemetry(
        provider,
        canvas=canvas,
        art_intent=_ART_INTENT,
        instruction="Make the tiny asset non-empty using bounded PixelProgram edits.",
        qa_evaluator=_NonEmptyQa(),
        budget=_BUDGET,
    )

    if provider.remaining != 0:
        raise AssertionError(f"recording left {provider.remaining} unconsumed provider calls")
    if len(provider.requests) != len(records):
        raise AssertionError("provider request count does not match the recording")
    if result.loop.status != "finished":
        raise AssertionError(f"expected finished loop, got {result.loop.status!r}")

    rgba = canvas.rgba_bytes()
    if rgba != _EXPECTED_FINAL_RGBA:
        raise AssertionError("recorded replay produced unexpected authoritative RGBA bytes")

    observation = result.loop.observation
    if observation["current"] != {"stage": None, "revision": 2}:
        raise AssertionError("recorded replay did not produce the expected revision state")
    if observation["qa"]["findings"]:
        raise AssertionError("recorded replay finished with deterministic QA findings")
    if len(observation["recent"]) != 2:
        raise AssertionError("recorded replay did not retain both bounded revision summaries")

    telemetry = result.telemetry
    expected_telemetry = {
        "schema": AGENT_COMPLEXITY_TELEMETRY_SCHEMA_V1,
        "input_tokens": 220,
        "output_tokens": 45,
        "tool_calls": 2,
        "operation_calls": 2,
        "visual_observation_calls": 0,
        "iterations": 2,
        "revisions": 2,
        "changed_pixels": 1,
        "api_cost_usd_micros": 110,
        "human_interventions": 0,
        "failure_category": None,
    }
    for field, expected in expected_telemetry.items():
        if telemetry[field] != expected:
            raise AssertionError(
                f"unexpected telemetry {field}: expected {expected!r}, got {telemetry[field]!r}"
            )
    if telemetry["exposed_concept_count"] <= 0:
        raise AssertionError("recorded replay exposed no provider-visible concepts")
    if telemetry["wall_time_ns"] < 0:
        raise AssertionError("wall time must be non-negative observational evidence")

    deterministic_telemetry = dict(telemetry)
    deterministic_telemetry.pop("wall_time_ns")
    return {
        "schema": SUMMARY_SCHEMA_V1,
        "record_count": len(records),
        "request_count": len(provider.requests),
        "status": result.loop.status,
        "final_rgba_sha256": sha256(rgba).hexdigest(),
        "observation": observation,
        "telemetry": deterministic_telemetry,
    }


def verify_checkpoint(path: Path = RECORDING_PATH) -> dict[str, Any]:
    """Replay the same recording twice and require deterministic non-timing evidence."""

    first = _run_once(path)
    second = _run_once(path)
    if first != second:
        raise AssertionError("recorded provider replay produced non-deterministic orchestration evidence")
    return first


def main(argv: Sequence[str] | None = None) -> None:
    if argv:
        raise SystemExit("P5-A4 checkpoint takes no arguments")
    summary = verify_checkpoint()
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":
    main()
