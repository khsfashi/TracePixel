from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence, cast

from tracepixel.preview.batch_review import (
    BatchReviewMember,
    BatchReviewTilePlacement,
    build_batch_review_package,
    validate_batch_review_package,
    write_batch_review_package,
)
from tracepixel.raster import Canvas, export_native_png

ROOT = Path(__file__).resolve().parents[2]
B3_ASSET_SET = ROOT / "evidence" / "p8_b3" / "reference-icon-prop-asset-set.v1.json"
B4_ASSET_SET = ROOT / "evidence" / "p8_b4" / "reference-tile-asset-set.v1.json"
B4_TOPOLOGY = ROOT / "evidence" / "p8_b4" / "reference-tile-topology.v1.json"
CORE_LANE = ROOT / "config" / "tracepixel.core-lane.json"

_EXPECTED_B3 = (
    "health-potion-icon",
    "iron-key-icon",
    "wooden-crate-prop",
    "lantern-prop",
)
_EXPECTED_B4 = (
    "grass-center-a",
    "grass-dirt-east-edge",
    "grass-center-b",
    "grass-dirt-southeast-corner",
)
_MEMBER_SHAPES = {
    "health-potion-icon": ("item-icon", 16, 16),
    "iron-key-icon": ("item-icon", 16, 16),
    "wooden-crate-prop": ("scene-prop", 24, 24),
    "lantern-prop": ("scene-prop", 24, 24),
    "grass-center-a": ("terrain-tile", 16, 16),
    "grass-dirt-east-edge": ("terrain-tile", 16, 16),
    "grass-center-b": ("terrain-tile", 16, 16),
    "grass-dirt-southeast-corner": ("terrain-tile", 16, 16),
}

TRANSPARENT = (0, 0, 0, 0)
OUTLINE = (45, 39, 43, 255)
RED_DARK = (132, 42, 49, 255)
RED = (210, 62, 68, 255)
RED_LIGHT = (244, 116, 100, 255)
GOLD_DARK = (129, 91, 36, 255)
GOLD = (217, 168, 70, 255)
GOLD_LIGHT = (250, 216, 124, 255)
WOOD_DARK = (91, 58, 39, 255)
WOOD = (151, 99, 57, 255)
WOOD_LIGHT = (194, 135, 71, 255)
GRASS_DARK = (57, 101, 57, 255)
GRASS = (84, 137, 70, 255)
GRASS_LIGHT = (119, 165, 82, 255)
DIRT_DARK = (114, 77, 48, 255)
DIRT = (154, 105, 62, 255)
DIRT_LIGHT = (189, 137, 79, 255)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _member_ids(asset_set: dict[str, object]) -> tuple[str, ...]:
    members = asset_set.get("members")
    if type(members) is not list:
        raise SystemExit("AssetSet members malformed")
    ids: list[str] = []
    for raw in cast(list[object], members):
        if type(raw) is not dict or type(cast(dict[str, object], raw).get("member_id")) is not str:
            raise SystemExit("AssetSet member malformed")
        ids.append(cast(str, cast(dict[str, object], raw)["member_id"]))
    return tuple(ids)


def _rect(canvas: Canvas, x: int, y: int, width: int, height: int, color: tuple[int, int, int, int]) -> None:
    edits = [
        (px, py, color)
        for py in range(y, y + height)
        for px in range(x, x + width)
    ]
    canvas.set_pixels(edits)


def _pixels(canvas: Canvas, coords: Sequence[tuple[int, int]], color: tuple[int, int, int, int]) -> None:
    canvas.set_pixels([(x, y, color) for x, y in coords])


def _potion() -> Canvas:
    canvas = Canvas(16, 16)
    _rect(canvas, 6, 2, 4, 2, OUTLINE)
    _rect(canvas, 7, 2, 2, 2, GOLD)
    _rect(canvas, 5, 4, 6, 2, OUTLINE)
    _rect(canvas, 4, 6, 8, 6, OUTLINE)
    _rect(canvas, 5, 6, 6, 5, RED_DARK)
    _rect(canvas, 6, 7, 4, 4, RED)
    _pixels(canvas, ((6, 7), (7, 7), (6, 8)), RED_LIGHT)
    _rect(canvas, 6, 12, 4, 1, OUTLINE)
    return canvas


def _key() -> Canvas:
    canvas = Canvas(16, 16)
    _rect(canvas, 2, 5, 6, 6, OUTLINE)
    _rect(canvas, 3, 6, 4, 4, GOLD)
    _rect(canvas, 4, 7, 2, 2, TRANSPARENT)
    _rect(canvas, 7, 7, 7, 3, OUTLINE)
    _rect(canvas, 7, 8, 6, 1, GOLD)
    _rect(canvas, 11, 9, 2, 2, OUTLINE)
    _rect(canvas, 12, 9, 1, 1, GOLD_LIGHT)
    return canvas


def _crate() -> Canvas:
    canvas = Canvas(24, 24)
    _rect(canvas, 3, 5, 18, 16, OUTLINE)
    _rect(canvas, 4, 6, 16, 14, WOOD)
    _rect(canvas, 4, 8, 16, 2, WOOD_LIGHT)
    _rect(canvas, 4, 15, 16, 2, WOOD_DARK)
    _rect(canvas, 7, 6, 2, 14, WOOD_DARK)
    _rect(canvas, 15, 6, 2, 14, WOOD_DARK)
    for offset in range(8):
        _pixels(canvas, ((6 + offset, 7 + offset), (17 - offset, 7 + offset)), OUTLINE)
    return canvas


def _lantern() -> Canvas:
    canvas = Canvas(24, 24)
    _rect(canvas, 9, 3, 6, 2, OUTLINE)
    _rect(canvas, 8, 5, 8, 2, OUTLINE)
    _rect(canvas, 7, 7, 10, 11, OUTLINE)
    _rect(canvas, 8, 8, 8, 9, GOLD_DARK)
    _rect(canvas, 9, 9, 6, 7, GOLD)
    _rect(canvas, 10, 10, 4, 5, GOLD_LIGHT)
    _rect(canvas, 9, 18, 6, 2, OUTLINE)
    _pixels(canvas, ((7, 5), (16, 5), (6, 6), (17, 6)), OUTLINE)
    return canvas


def _grass_base(variant: int) -> Canvas:
    canvas = Canvas(16, 16)
    _rect(canvas, 0, 0, 16, 16, GRASS)
    coords = (
        ((2, 3), (8, 2), (13, 5), (5, 10), (11, 12), (3, 14))
        if variant == 0
        else ((3, 2), (10, 4), (14, 8), (6, 12), (1, 10), (12, 14))
    )
    _pixels(canvas, coords, GRASS_LIGHT)
    _pixels(canvas, tuple((x, min(15, y + 1)) for x, y in coords[:3]), GRASS_DARK)
    return canvas


def _east_edge() -> Canvas:
    canvas = _grass_base(0)
    _rect(canvas, 12, 0, 4, 16, DIRT)
    _rect(canvas, 13, 0, 3, 16, DIRT_LIGHT)
    for y in (2, 5, 9, 13):
        _pixels(canvas, ((11, y), (12, y + 1)), DIRT_DARK)
    _rect(canvas, 0, 15, 12, 1, GRASS)
    return canvas


def _southeast_corner() -> Canvas:
    canvas = _grass_base(1)
    _rect(canvas, 12, 0, 4, 16, DIRT)
    _rect(canvas, 0, 12, 16, 4, DIRT)
    _rect(canvas, 13, 0, 3, 13, DIRT_LIGHT)
    _rect(canvas, 0, 13, 16, 3, DIRT_LIGHT)
    _pixels(canvas, ((11, 4), (11, 8), (4, 11), (8, 11), (11, 11)), DIRT_DARK)
    return canvas


def _fixture_canvas(member_id: str) -> Canvas:
    if member_id == "health-potion-icon":
        return _potion()
    if member_id == "iron-key-icon":
        return _key()
    if member_id == "wooden-crate-prop":
        return _crate()
    if member_id == "lantern-prop":
        return _lantern()
    if member_id == "grass-center-a":
        return _grass_base(0)
    if member_id == "grass-dirt-east-edge":
        return _east_edge()
    if member_id == "grass-center-b":
        return _grass_base(1)
    if member_id == "grass-dirt-southeast-corner":
        return _southeast_corner()
    raise SystemExit(f"unknown P8-B5 fixture member: {member_id}")


def _review_members() -> tuple[BatchReviewMember, ...]:
    members: list[BatchReviewMember] = []
    for member_id in _EXPECTED_B3 + _EXPECTED_B4:
        asset_class, width, height = _MEMBER_SHAPES[member_id]
        canvas = _fixture_canvas(member_id)
        if (canvas.width, canvas.height) != (width, height):
            raise SystemExit(f"fixture canvas drifted for {member_id}")
        png = export_native_png(canvas)
        members.append(
            BatchReviewMember(
                member_id=member_id,
                asset_class=asset_class,
                width=width,
                height=height,
                png=png.png,
                source_kind="presentation-fixture",
                source_ref=f"evidence/p8_b5/presentation-fixture/{member_id}",
            )
        )
    return tuple(members)


def _tile_layout() -> tuple[BatchReviewTilePlacement, ...]:
    topology = _json(B4_TOPOLOGY)
    layout = topology.get("layout")
    raw_members = topology.get("members")
    if type(layout) is not dict or cast(dict[str, object], layout) != {"columns": 2, "rows": 2}:
        raise SystemExit("P8-B4 topology layout drifted")
    if type(raw_members) is not list:
        raise SystemExit("P8-B4 topology members malformed")

    placements: list[BatchReviewTilePlacement] = []
    ids: list[str] = []
    for raw in cast(list[object], raw_members):
        if type(raw) is not dict:
            raise SystemExit("P8-B4 topology member malformed")
        member = cast(dict[str, object], raw)
        member_id = member.get("member_id")
        x = member.get("x")
        y = member.get("y")
        if type(member_id) is not str or type(x) is not int or type(y) is not int:
            raise SystemExit("P8-B4 topology placement malformed")
        ids.append(member_id)
        placements.append(BatchReviewTilePlacement(member_id=member_id, x=x, y=y))
    if tuple(ids) != _EXPECTED_B4:
        raise SystemExit("P8-B4 topology member order drifted")
    return tuple(placements)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build/validate the P8-B5 batch mobile-review surface.")
    parser.add_argument(
        "--output",
        type=Path,
        help="optional empty/non-existent directory to materialize the bilingual review package",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    if _member_ids(_json(B3_ASSET_SET)) != _EXPECTED_B3:
        raise SystemExit("P8-B3 representative member set drifted")
    if _member_ids(_json(B4_ASSET_SET)) != _EXPECTED_B4:
        raise SystemExit("P8-B4 representative member set drifted")

    members = _review_members()
    package = build_batch_review_package(members, tile_layout=_tile_layout())
    validate_batch_review_package(package)

    if package.manifest["review_scope"] != "presentation-fixture":
        raise SystemExit("CI fixture must never masquerade as retained production output")
    manifest_members = cast(list[dict[str, object]], package.manifest["members"])
    if [member["member_id"] for member in manifest_members] != list(_EXPECTED_B3 + _EXPECTED_B4):
        raise SystemExit("batch review must preserve upstream declared member order")
    if package.manifest["tile_layout"] != {
        "columns": 2,
        "rows": 2,
        "placements": [
            {"member_id": "grass-center-a", "x": 0, "y": 0},
            {"member_id": "grass-dirt-east-edge", "x": 1, "y": 0},
            {"member_id": "grass-center-b", "x": 0, "y": 1},
            {"member_id": "grass-dirt-southeast-corner", "x": 1, "y": 1},
        ],
    }:
        raise SystemExit("tile patch projection drifted")

    presentation = cast(dict[str, object], package.manifest["presentation"])
    if presentation["scripts"] != 0 or presentation["external_dependencies"] != 0:
        raise SystemExit("P8-B5 review surface must remain script/network independent")
    if presentation["inspection_scaling"] != "css-nearest-neighbor":
        raise SystemExit("P8-B5 must not allocate duplicate enlarged raster evidence")

    authority = cast(dict[str, object], package.manifest["authority"])
    if authority["human_judgment_is_deterministic_qa"] is not False:
        raise SystemExit("human aesthetic review cannot become deterministic QA truth")
    perceptual = set(cast(list[str], authority["perceptual_only"]))
    required = {
        "cross-asset-style-coherence",
        "palette-coherence",
        "tile-pixel-seam-quality",
        "native-1x-readability",
        "mobile-scanability",
    }
    if not required.issubset(perceptual):
        raise SystemExit("P8-B5 perceptual review dimensions drifted")

    lane = _json(CORE_LANE)
    if lane.get("current") != "P8" or lane.get("current_child") != "P8-B5" or lane.get("active_issue") != 92:
        raise SystemExit("P8-B5 checkpoint requires live P8-B5 / issue #92")

    if args.output is not None:
        write_batch_review_package(package, args.output)

    print(
        json.dumps(
            {
                "schema": "tracepixel.p8-b5-checkpoint.v1",
                "member_count": len(members),
                "tile_patch": [2, 2],
                "languages": ["en", "ko"],
                "review_scope": "presentation-fixture",
                "scripts": 0,
                "external_dependencies": 0,
                "enlarged_raster_copies": 0,
                "production_quality_claim": False,
                "owner_review_required_before_p8_b6": True,
                "next_action": "retained-output-mobile-review",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
