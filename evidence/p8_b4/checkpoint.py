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
ASSET_SET = ROOT / "evidence" / "p8_b4" / "reference-tile-asset-set.v1.json"
TOPOLOGY = ROOT / "evidence" / "p8_b4" / "reference-tile-topology.v1.json"
REQUEST_ROOT = ROOT / "evidence" / "p8_b4"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"

_EXPECTED_MEMBER_IDS = (
    "grass-center-a",
    "grass-dirt-east-edge",
    "grass-center-b",
    "grass-dirt-southeast-corner",
)
_EXPECTED_ROLES = {
    "grass-center-a": "center-variant",
    "grass-dirt-east-edge": "edge",
    "grass-center-b": "center-variant",
    "grass-dirt-southeast-corner": "corner",
}
_EDGE_KEYS = frozenset(("top", "right", "bottom", "left"))
_ALLOWED_TERRAINS = frozenset(("grass", "dirt"))


class TileTopologyError(ValueError):
    pass


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


def _topology_error(message: str) -> None:
    raise TileTopologyError(message)


def _validate_topology(
    topology: object,
    asset_set: dict[str, object],
) -> dict[tuple[int, int], dict[str, str]]:
    if type(topology) is not dict:
        _topology_error("topology must be a JSON object")
    root = cast(dict[str, object], topology)
    if frozenset(root) != frozenset(("schema", "asset_set_id", "tile_size", "layout", "members")):
        _topology_error("topology fields drifted")
    if root["schema"] != "tracepixel.p8-b4-tile-topology.v1":
        _topology_error("topology schema drifted")
    if root["asset_set_id"] != asset_set["asset_set_id"]:
        _topology_error("topology asset_set_id does not match AssetSet")

    tile_size = root["tile_size"]
    if type(tile_size) is not dict or cast(dict[str, object], tile_size) != {"width": 16, "height": 16}:
        _topology_error("B4 topology must retain exact 16x16 tile size")

    layout = root["layout"]
    if type(layout) is not dict or cast(dict[str, object], layout) != {"columns": 2, "rows": 2}:
        _topology_error("B4 topology must retain the frozen 2x2 patch layout")

    raw_members = root["members"]
    asset_members = asset_set["members"]
    if type(raw_members) is not list or type(asset_members) is not list:
        _topology_error("topology or AssetSet member list malformed")
    if len(raw_members) != 4:
        _topology_error("B4 topology must retain four representative tiles")

    declared_ids = [
        cast(str, member["member_id"])
        for member in cast(list[dict[str, object]], asset_members)
    ]
    topology_ids: list[str] = []
    by_coord: dict[tuple[int, int], dict[str, str]] = {}

    for raw in cast(list[object], raw_members):
        if type(raw) is not dict:
            _topology_error("topology member malformed")
        member = cast(dict[str, object], raw)
        if frozenset(member) != frozenset(("member_id", "x", "y", "role", "edges")):
            _topology_error("topology member fields drifted")
        member_id = member["member_id"]
        x = member["x"]
        y = member["y"]
        role = member["role"]
        edges = member["edges"]
        if type(member_id) is not str or member_id not in _EXPECTED_ROLES:
            _topology_error("unexpected topology member id")
        if role != _EXPECTED_ROLES[member_id]:
            _topology_error(f"unexpected role for {member_id}")
        if type(x) is not int or type(y) is not int or not (0 <= x < 2 and 0 <= y < 2):
            _topology_error(f"invalid tile coordinate for {member_id}")
        if type(edges) is not dict or frozenset(cast(dict[str, object], edges)) != _EDGE_KEYS:
            _topology_error(f"edge contract malformed for {member_id}")
        typed_edges = cast(dict[str, object], edges)
        if any(type(value) is not str or value not in _ALLOWED_TERRAINS for value in typed_edges.values()):
            _topology_error(f"unsupported terrain label for {member_id}")
        coord = (x, y)
        if coord in by_coord:
            _topology_error(f"duplicate tile coordinate {coord!r}")
        topology_ids.append(member_id)
        by_coord[coord] = cast(dict[str, str], dict(typed_edges))

    if topology_ids != declared_ids or tuple(topology_ids) != _EXPECTED_MEMBER_IDS:
        _topology_error("topology member order must equal the frozen AssetSet order")
    if set(by_coord) != {(0, 0), (1, 0), (0, 1), (1, 1)}:
        _topology_error("topology must fill the frozen 2x2 patch exactly")

    for y in range(2):
        if by_coord[(0, y)]["right"] != by_coord[(1, y)]["left"]:
            _topology_error(f"horizontal semantic seam mismatch on row {y}")
    for x in range(2):
        if by_coord[(x, 0)]["bottom"] != by_coord[(x, 1)]["top"]:
            _topology_error(f"vertical semantic seam mismatch on column {x}")

    return by_coord


class _TileBreadthExecutor:
    """Provider-free seam probe; tile members still use the single-asset authority."""

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
        del context
        asset_class = _asset_class(request)
        with self._lock:
            self.calls[member_id] = self.calls.get(member_id, 0) + 1
            self.classes[member_id] = asset_class

        if member_id == "grass-dirt-southeast-corner":
            return SingleAssetExecutionOutput(
                status="failed",
                failure_category="recorded.tile_breadth_probe_failure",
                failure_reason="synthetic provider-free tile member failure",
            )

        return SingleAssetExecutionOutput(
            status="succeeded",
            result_ref=f"results/{member_id}.json",
            result_sha256=_digest(f"p8-b4:{member_id}:{request_sha256}"),
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
    actual_ids = tuple(cast(str, member["member_id"]) for member in members)
    if actual_ids != _EXPECTED_MEMBER_IDS:
        raise SystemExit(f"tile member order drifted: {actual_ids!r}")

    canvas_sizes: dict[str, tuple[int, int]] = {}
    classes: dict[str, str] = {}
    for member in members:
        member_id = cast(str, member["member_id"])
        ref = cast(str, member["request_ref"])
        payload = payloads[ref]
        classes[member_id] = _asset_class(payload)
        canvas_sizes[member_id] = _canvas_size(payload)
    if set(classes.values()) != {"terrain-tile"}:
        raise SystemExit(f"B4 fixture must remain terrain-tile only: {classes!r}")
    if set(canvas_sizes.values()) != {(16, 16)}:
        raise SystemExit("B4 fixture must retain one exact 16x16 tile grid")

    topology = _json(TOPOLOGY)
    semantic_edges = _validate_topology(topology, asset_set)
    tampered = json.loads(json.dumps(topology))
    cast(dict[str, object], cast(list[object], cast(dict[str, object], tampered)["members"])[3])["edges"] = {
        "top": "dirt",
        "right": "dirt",
        "bottom": "dirt",
        "left": "grass",
    }
    try:
        _validate_topology(tampered, asset_set)
    except TileTopologyError:
        pass
    else:
        raise SystemExit("tampered tile semantic seam must fail closed")

    consistency = build_asset_set_consistency(request_set, asset_set, payloads)
    validate_asset_set_consistency(consistency, request_set, asset_set, payloads)
    style = consistency["style_profile"]
    palette = consistency["palette_profile"]
    if type(style) is not dict or style.get("profile_id") != "top-down-rpg-tiles":
        raise SystemExit("tile set lost its exact shared style binding")
    if type(palette) is not dict or palette.get("profile_id") != "meadow-dirt-palette":
        raise SystemExit("tile set lost its exact shared palette binding")
    if consistency["visual_style_policy"] != "perceptual-evidence-required":
        raise SystemExit("B4 must keep visual style appearance perceptual")
    if consistency["visual_palette_policy"] != "perceptual-evidence-required":
        raise SystemExit("B4 must keep visual palette appearance perceptual")

    executor = _TileBreadthExecutor()
    report = execute_asset_set_schedule(
        schedule,
        request_set,
        asset_set,
        payloads,
        executor,
    )

    if executor.calls != {member_id: 1 for member_id in _EXPECTED_MEMBER_IDS}:
        raise SystemExit("tile members were restarted or skipped")
    if executor.classes != {member_id: "terrain-tile" for member_id in _EXPECTED_MEMBER_IDS}:
        raise SystemExit("single-asset execution seam did not preserve terrain-tile class")
    if report["failed_member_ids"] != ["grass-dirt-southeast-corner"]:
        raise SystemExit("tile member failure was not isolated exactly")
    statuses = {
        cast(str, member["member_id"]): member["status"]
        for member in cast(list[dict[str, object]], report["members"])
    }
    if statuses != {
        "grass-center-a": "succeeded",
        "grass-dirt-east-edge": "succeeded",
        "grass-center-b": "succeeded",
        "grass-dirt-southeast-corner": "failed",
    }:
        raise SystemExit(f"unexpected tile execution statuses: {statuses!r}")
    if report["aggregate_provider_calls"] != 0:
        raise SystemExit("B4 breadth checkpoint must add zero provider calls")
    if report["aggregate_input_tokens"] != 0 or report["aggregate_output_tokens"] != 0:
        raise SystemExit("B4 breadth checkpoint must add zero provider tokens")
    if report["aggregate_pixel_edits"] != 0:
        raise SystemExit("B4 breadth checkpoint must create no raster work")
    if report["scheduler_provider_calls"] != 0:
        raise SystemExit("scheduler provider calls must remain zero")

    lane = _json(CORE_LANE)
    if lane.get("current") != "P8" or lane.get("active_issue") != 92:
        raise SystemExit("P8-B4 checkpoint requires live P8 / issue #92")
    children = lane.get("child_sequences")
    if type(children) is not dict:
        raise SystemExit("core lane child_sequences malformed")
    p8 = cast(dict[str, object], children).get("P8")
    child = lane.get("current_child")
    if type(p8) is not list or child not in cast(list[object], p8):
        raise SystemExit("active P8 child is not declared")
    names = cast(list[str], p8)
    if names.index(cast(str, child)) < names.index("P8-B5"):
        raise SystemExit("P8-B4 completion must hand off to P8-B5 before this checkpoint is green")

    print(
        json.dumps(
            {
                "schema": "tracepixel.p8-b4-checkpoint.v1",
                "member_count": len(members),
                "asset_class": "terrain-tile",
                "tile_size": [16, 16],
                "semantic_seams_checked": 4,
                "semantic_edge_labels": sorted({value for edges in semantic_edges.values() for value in edges.values()}),
                "shared_style_profile": style.get("profile_id"),
                "shared_palette_profile": palette.get("profile_id"),
                "pixel_seam_authority": "perceptual-evidence-required",
                "failure_isolation": True,
                "provider_calls_added": 0,
                "provider_tokens_added": 0,
                "raster_authority_added": False,
                "new_single_asset_path_added": False,
                "next_child": "P8-B5",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
