from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from threading import Lock
from typing import cast

from tracepixel.model.asset_set_consistency_validation import (
    build_asset_set_consistency,
    validate_asset_set_consistency,
)
from tracepixel.model.asset_set_executor import (
    AssetSetMemberExecutionContext,
    SingleAssetExecutionOutput,
    execute_asset_set_schedule,
)
from tracepixel.model.asset_set_schedule import ASSET_SET_REQUEST_SCHEMA_V1
from tracepixel.model.asset_set_schedule_validation import (
    asset_request_sha256,
    asset_set_sha256,
    build_asset_set_schedule,
    validate_asset_set_schedule,
)
from tracepixel.model.asset_set_validation import validate_asset_set

ROOT = Path(__file__).resolve().parents[2]
ASSET_SET = ROOT / "evidence" / "p8_b3" / "reference-icon-prop-asset-set.v1.json"
REQUEST_ROOT = ROOT / "evidence" / "p8_b3"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"

_EXPECTED_CLASSES = {
    "health-potion-icon": "item-icon",
    "iron-key-icon": "item-icon",
    "wooden-crate-prop": "scene-prop",
    "lantern-prop": "scene-prop",
}


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _payloads(asset_set: dict[str, object]) -> dict[str, object]:
    raw_members = asset_set.get("members")
    if type(raw_members) is not list:
        raise SystemExit("AssetSet members malformed")

    result: dict[str, object] = {}
    for raw in cast(list[object], raw_members):
        if type(raw) is not dict:
            raise SystemExit("AssetSet member malformed")
        ref = cast(dict[str, object], raw).get("request_ref")
        if type(ref) is not str:
            raise SystemExit("request_ref malformed")
        result[ref] = _json(REQUEST_ROOT / ref)
    return result


def _request_set(
    asset_set: dict[str, object],
    payloads: dict[str, object],
) -> dict[str, object]:
    raw_members = asset_set["members"]
    shared = asset_set["shared_profiles"]
    if type(raw_members) is not list:
        raise SystemExit("AssetSet members malformed")

    return {
        "schema": ASSET_SET_REQUEST_SCHEMA_V1,
        "asset_set_id": asset_set["asset_set_id"],
        "asset_set_sha256": asset_set_sha256(asset_set),
        "members": [
            {
                "member_id": member["member_id"],
                "request_ref": member["request_ref"],
                "request_sha256": asset_request_sha256(
                    payloads[cast(str, member["request_ref"])],
                    shared_profiles=shared,
                ),
            }
            for member in cast(list[dict[str, object]], raw_members)
        ],
    }


def _asset_class(payload: object) -> str:
    if type(payload) is not dict:
        raise SystemExit("member request payload malformed")
    intent = cast(dict[str, object], payload).get("art_intent")
    if type(intent) is not dict:
        raise SystemExit("member art_intent malformed")
    asset_class = cast(dict[str, object], intent).get("asset_class")
    if type(asset_class) is not str:
        raise SystemExit("member asset_class malformed")
    return asset_class


def _canvas_size(payload: object) -> tuple[int, int]:
    if type(payload) is not dict:
        raise SystemExit("member request payload malformed")
    intent = cast(dict[str, object], payload).get("art_intent")
    if type(intent) is not dict:
        raise SystemExit("member art_intent malformed")
    canvas = cast(dict[str, object], intent).get("canvas")
    if type(canvas) is not dict:
        raise SystemExit("member canvas malformed")
    width = cast(dict[str, object], canvas).get("width")
    height = cast(dict[str, object], canvas).get("height")
    if type(width) is not int or type(height) is not int:
        raise SystemExit("member canvas size malformed")
    return width, height


class _BreadthExecutor:
    """Provider-free seam probe; no second authoring path or raster authority."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}
        self.classes: dict[str, str] = {}
        self._lock = Lock()

    def execute(
        self,
        request: object,
        /,
        *,
        member_id: str,
        request_sha256: str,
        context: AssetSetMemberExecutionContext,
    ) -> SingleAssetExecutionOutput:
        asset_class = _asset_class(request)
        with self._lock:
            self.calls[member_id] = self.calls.get(member_id, 0) + 1
            self.classes[member_id] = asset_class

        if member_id == "lantern-prop":
            return SingleAssetExecutionOutput(
                status="failed",
                failure_category="recorded.breadth_probe_failure",
                failure_reason="synthetic provider-free member failure",
            )

        return SingleAssetExecutionOutput(
            status="succeeded",
            result_ref=f"results/{member_id}.json",
            result_sha256=_digest(f"p8-b3:{member_id}:{request_sha256}"),
            deterministic_qa_ref=f"qa/{member_id}.json",
            perceptual_ref=f"perceptual/{member_id}.json",
            complexity_ref=f"complexity/{member_id}.json",
            provenance_ref=f"provenance/{member_id}.json",
        )


def main() -> int:
    asset_set = validate_asset_set(_json(ASSET_SET))
    payloads = _payloads(asset_set)
    request_set = _request_set(asset_set, payloads)
    schedule = build_asset_set_schedule(request_set, asset_set, payloads)
    validate_asset_set_schedule(schedule, request_set, asset_set, payloads)

    members = cast(list[dict[str, object]], schedule["members"])
    actual_classes: dict[str, str] = {}
    canvas_sizes: dict[str, tuple[int, int]] = {}
    for member in members:
        member_id = cast(str, member["member_id"])
        ref = cast(str, member["request_ref"])
        actual_classes[member_id] = _asset_class(payloads[ref])
        canvas_sizes[member_id] = _canvas_size(payloads[ref])

    if actual_classes != _EXPECTED_CLASSES:
        raise SystemExit(f"mixed icon/prop class fixture drifted: {actual_classes!r}")
    if set(canvas_sizes.values()) != {(16, 16), (24, 24)}:
        raise SystemExit("B3 fixture must retain independent 16x16 icon and 24x24 prop canvases")

    consistency = build_asset_set_consistency(request_set, asset_set, payloads)
    validate_asset_set_consistency(consistency, request_set, asset_set, payloads)
    style = consistency["style_profile"]
    if type(style) is not dict or style.get("profile_id") != "small-rpg-objects":
        raise SystemExit("mixed icon/prop set lost its exact shared style binding")
    if consistency["visual_style_policy"] != "perceptual-evidence-required":
        raise SystemExit("B3 must not promote visual style appearance to deterministic truth")

    executor = _BreadthExecutor()
    report = execute_asset_set_schedule(
        schedule,
        request_set,
        asset_set,
        payloads,
        executor,
    )

    if executor.calls != {member_id: 1 for member_id in _EXPECTED_CLASSES}:
        raise SystemExit("mixed-class members were restarted or skipped")
    if executor.classes != _EXPECTED_CLASSES:
        raise SystemExit("single-asset execution seam did not preserve member asset_class")
    if report["failed_member_ids"] != ["lantern-prop"]:
        raise SystemExit("cross-class member failure was not isolated exactly")
    statuses = {
        cast(str, member["member_id"]): member["status"]
        for member in cast(list[dict[str, object]], report["members"])
    }
    if statuses != {
        "health-potion-icon": "succeeded",
        "iron-key-icon": "succeeded",
        "wooden-crate-prop": "succeeded",
        "lantern-prop": "failed",
    }:
        raise SystemExit(f"unexpected mixed-class execution statuses: {statuses!r}")
    if report["aggregate_provider_calls"] != 0:
        raise SystemExit("B3 breadth checkpoint must add zero provider calls")
    if report["aggregate_input_tokens"] != 0 or report["aggregate_output_tokens"] != 0:
        raise SystemExit("B3 breadth checkpoint must add zero provider tokens")
    if report["aggregate_pixel_edits"] != 0:
        raise SystemExit("B3 breadth checkpoint must create no raster work")
    if report["scheduler_provider_calls"] != 0:
        raise SystemExit("scheduler provider calls must remain zero")

    lane = _json(CORE_LANE)
    if lane.get("current") != "P8" or lane.get("active_issue") != 92:
        raise SystemExit("P8-B3 checkpoint requires live P8 / issue #92")
    if lane.get("current_child") != "P8-B4":
        raise SystemExit("P8-B3 checkpoint expects merge handoff to P8-B4")

    print(
        json.dumps(
            {
                "schema": "tracepixel.p8-b3-checkpoint.v1",
                "member_count": len(members),
                "asset_classes": actual_classes,
                "canvas_sizes": {key: list(value) for key, value in canvas_sizes.items()},
                "shared_style_profile": style.get("profile_id"),
                "failure_isolation": True,
                "provider_calls_added": 0,
                "provider_tokens_added": 0,
                "raster_authority_added": False,
                "new_single_asset_path_added": False,
                "next_child": "P8-B4",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
