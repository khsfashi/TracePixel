from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tracepixel.raster.canvas import Canvas
from tracepixel.raster.export import export_native_png, export_nearest_preview_png

FIXTURE_SCHEMA = "tracepixel.replay-fixture.v1"
FIXTURE_ID = "p1-r3-potion-v1"
PREVIEW_SCALE = 4
PALETTE = {
    ".": (0, 0, 0, 0),
    "K": (35, 28, 45, 255),
    "C": (164, 105, 57, 255),
    "H": (225, 166, 88, 255),
    "B": (132, 190, 230, 255),
    "G": (76, 122, 176, 255),
    "R": (192, 48, 68, 255),
    "L": (246, 104, 104, 255),
}
ROWS = (
    "................",
    "......CCCC......",
    ".....CHHHC......",
    ".....KKKKK......",
    "......KKK.......",
    ".....KBBBK......",
    "....KBGGGBK.....",
    "...KBGGGGGBK....",
    "...KBBRRRBBK....",
    "..KBRRRRRRBK....",
    "..KRRRLLRRRK....",
    "..KRRLLLLRRK....",
    "...KRRRRRRK.....",
    "....KRRRRK......",
    ".....KKKK.......",
    "................",
)


def fixture_program_bytes() -> bytes:
    payload = {
        "palette": {key: list(value) for key, value in PALETTE.items()},
        "rows": list(ROWS),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def render_fixture() -> Canvas:
    canvas = Canvas(16, 16)
    edits = []
    for y, row in enumerate(ROWS):
        if len(row) != 16:
            raise AssertionError("fixture row width drifted")
        for x, token in enumerate(row):
            if token != ".":
                edits.append((x, y, PALETTE[token]))
    canvas.set_pixels(edits)
    return canvas


def build_evidence() -> tuple[bytes, bytes, bytes, dict[str, object]]:
    canvas = render_fixture()
    rgba = canvas.rgba_bytes()
    native = export_native_png(canvas)
    preview = export_nearest_preview_png(canvas, scale=PREVIEW_SCALE)
    manifest = {
        "schema": "tracepixel.p1-r3-evidence.v1",
        "fixture": {
            "schema": FIXTURE_SCHEMA,
            "id": FIXTURE_ID,
            "width": canvas.width,
            "height": canvas.height,
            "program_sha256": hashlib.sha256(fixture_program_bytes()).hexdigest(),
            "edit_count": sum(token != "." for row in ROWS for token in row),
            "authoritative_rgba_sha256": hashlib.sha256(rgba).hexdigest(),
        },
        "outputs": {
            "authoritative_rgba": "potion.rgba",
            "native_png": "potion.png",
            "preview_png": "potion@4x.png",
            "native": native.metadata.as_dict(),
            "preview": preview.metadata.as_dict(),
        },
    }
    return rgba, native.png, preview.png, manifest


def write_evidence(directory: Path) -> None:
    rgba, native_png, preview_png, manifest = build_evidence()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "potion.rgba").write_bytes(rgba)
    (directory / "potion.png").write_bytes(native_png)
    (directory / "potion@4x.png").write_bytes(preview_png)
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_evidence(Path(__file__).resolve().parent)
