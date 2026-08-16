from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from tracepixel.model import STAGE_SEQUENCE_V1, StageIdV1

from .bundle import PreviewStageArtifact

STAGE_CONTACT_SHEET_SCHEMA_V1 = "tracepixel.stage-contact-sheet.v1"

_MAX_COLUMNS = len(STAGE_SEQUENCE_V1)
_MAX_STAGE_IMAGE_DIMENSION = 4096
_STAGE_ORDER = {stage: index for index, stage in enumerate(STAGE_SEQUENCE_V1)}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SAFE_FILENAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)

_GAP = 8
_PADDING = 8
_LABEL_HEIGHT = 30
_MIN_CELL_WIDTH = 112
_LABEL_FONT_SIZE = 10
_INDEX_FONT_SIZE = 9


class StageContactSheetContractError(ValueError):
    """Stable deterministic rejection for malformed P6-V1 contact-sheet input."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


@dataclass(frozen=True, slots=True)
class StageContactSheet:
    manifest: dict[str, object]
    svg: bytes


def _fail(code: str, path: str, message: str) -> None:
    raise StageContactSheetContractError(code, path, message)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _validate_name(name: object, path: str) -> str:
    if type(name) is not str or not name:
        _fail("invalid_stage_image_name", path, "must be a non-empty filename")
    text = name
    if (
        text in (".", "..")
        or "/" in text
        or "\\" in text
        or any(character not in _SAFE_FILENAME_CHARS for character in text)
    ):
        _fail(
            "invalid_stage_image_name",
            path,
            "must be one safe filename using letters, digits, '.', '_', or '-'",
        )
    return text


def _png_dimensions(data: object, path: str) -> tuple[int, int]:
    if type(data) is not bytes:
        _fail("invalid_stage_png", path, "must be bytes")
    png = data
    if len(png) < 33 or not png.startswith(_PNG_SIGNATURE):
        _fail("invalid_stage_png", path, "must be a complete PNG beginning with the PNG signature")
    ihdr_length = struct.unpack(">I", png[8:12])[0]
    if ihdr_length != 13 or png[12:16] != b"IHDR":
        _fail("invalid_stage_png", path, "must begin with a standard 13-byte IHDR chunk")

    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", png[16:29]
    )
    if (
        width < 1
        or height < 1
        or width > _MAX_STAGE_IMAGE_DIMENSION
        or height > _MAX_STAGE_IMAGE_DIMENSION
    ):
        _fail(
            "invalid_stage_png_dimensions",
            path,
            f"width and height must be in [1, {_MAX_STAGE_IMAGE_DIMENSION}]",
        )
    if bit_depth != 8 or color_type != 6:
        _fail(
            "unsupported_stage_png_format",
            path,
            "must be an 8-bit RGBA PNG",
        )
    if compression != 0 or filter_method != 0 or interlace != 0:
        _fail(
            "unsupported_stage_png_format",
            path,
            "must use baseline PNG compression/filter methods without interlacing",
        )
    return width, height


def build_stage_contact_sheet(
    stage_artifacts: tuple[PreviewStageArtifact, ...] | list[PreviewStageArtifact],
    *,
    columns: int = 3,
) -> StageContactSheet:
    """Compose authored stage PNGs into one deterministic SVG review sheet.

    PNG bytes are embedded byte-for-byte as data URIs. The sheet never decodes,
    resamples, or re-encodes source pixels. Presentation cells keep a minimum
    width so fixed P3 stage labels remain readable on phone-sized review pages.
    """

    if type(columns) is not int or columns < 1 or columns > _MAX_COLUMNS:
        _fail(
            "invalid_columns",
            "$.columns",
            f"must be an exact integer in [1, {_MAX_COLUMNS}]",
        )

    normalized: list[tuple[int, PreviewStageArtifact, str, int, int]] = []
    seen_stages: set[StageIdV1] = set()
    for index, artifact in enumerate(stage_artifacts):
        path = f"$.stage_artifacts[{index}]"
        if not isinstance(artifact, PreviewStageArtifact):
            _fail("invalid_stage_artifact", path, "must be PreviewStageArtifact")
        if artifact.kind != "stage-image":
            continue
        if artifact.stage not in _STAGE_ORDER:
            _fail("invalid_stage", f"{path}.stage", "must be a supported P3 stage")
        if artifact.stage in seen_stages:
            _fail(
                "duplicate_stage_image",
                f"{path}.stage",
                f"stage {artifact.stage!r} already has a contact-sheet image",
            )
        seen_stages.add(artifact.stage)
        if artifact.media_type != "image/png":
            _fail(
                "invalid_stage_image_media_type",
                f"{path}.media_type",
                "stage-image artifacts must use image/png",
            )
        name = _validate_name(artifact.name, f"{path}.name")
        width, height = _png_dimensions(artifact.data, f"{path}.data")
        normalized.append((_STAGE_ORDER[artifact.stage], artifact, name, width, height))

    if not normalized:
        _fail(
            "no_stage_images",
            "$.stage_artifacts",
            "at least one stage-image PNG is required",
        )

    normalized.sort(key=lambda item: item[0])
    frame_count = len(normalized)
    columns_used = min(columns, frame_count)
    rows = (frame_count + columns_used - 1) // columns_used
    max_width = max(item[3] for item in normalized)
    max_height = max(item[4] for item in normalized)
    cell_width = max(_MIN_CELL_WIDTH, max_width + _PADDING * 2)
    cell_height = _LABEL_HEIGHT + max_height + _PADDING * 2
    sheet_width = _GAP + columns_used * (cell_width + _GAP)
    sheet_height = _GAP + rows * (cell_height + _GAP)

    lines = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {sheet_width} {sheet_height}" '
            f'width="{sheet_width}" height="{sheet_height}" shape-rendering="crispEdges">'
        ),
        '<rect width="100%" height="100%" fill="#eeeeee"/>',
    ]
    frames: list[dict[str, object]] = []

    for index, (_, artifact, name, width, height) in enumerate(normalized, start=1):
        zero_index = index - 1
        column = zero_index % columns_used
        row = zero_index // columns_used
        cell_x = _GAP + column * (cell_width + _GAP)
        cell_y = _GAP + row * (cell_height + _GAP)
        image_x = cell_x + (cell_width - width) // 2
        image_y = cell_y + _PADDING + _LABEL_HEIGHT
        label = artifact.stage.replace("_", " ")
        encoded = base64.b64encode(artifact.data).decode("ascii")
        source_digest = sha256(artifact.data).hexdigest()
        source_path = f"stages/{artifact.stage}/{name}"

        lines.extend(
            (
                f'<g id="{index:02d}-{artifact.stage}" transform="translate({cell_x} {cell_y})">',
                f'<rect width="{cell_width}" height="{cell_height}" fill="#ffffff" stroke="#c8c8c8"/>',
                (
                    f'<text x="{_PADDING}" y="{_PADDING + 8}" '
                    f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
                    f'font-size="{_INDEX_FONT_SIZE}" fill="#666666">{index:02d}</text>'
                ),
                (
                    f'<text x="{_PADDING}" y="{_PADDING + 21}" '
                    f'font-family="ui-sans-serif, system-ui, sans-serif" '
                    f'font-size="{_LABEL_FONT_SIZE}" font-weight="600" fill="#202020">'
                    f"{label}</text>"
                ),
                (
                    f'<image x="{image_x - cell_x}" y="{image_y - cell_y}" '
                    f'width="{width}" height="{height}" preserveAspectRatio="none" '
                    f'image-rendering="pixelated" data-source-sha256="{source_digest}" '
                    f'href="data:image/png;base64,{encoded}"/>'
                ),
                "</g>",
            )
        )
        frames.append(
            {
                "stage": artifact.stage,
                "source_path": source_path,
                "source_sha256": source_digest,
                "source_size_bytes": len(artifact.data),
                "source_width": width,
                "source_height": height,
                "image_x": image_x,
                "image_y": image_y,
            }
        )

    lines.append("</svg>")
    svg = ("\n".join(lines) + "\n").encode("utf-8")
    manifest: dict[str, object] = {
        "schema": STAGE_CONTACT_SHEET_SCHEMA_V1,
        "sheet": {
            "path": "stage-contact-sheet.svg",
            "media_type": "image/svg+xml",
            "size_bytes": len(svg),
            "sha256": sha256(svg).hexdigest(),
        },
        "layout": {
            "columns": columns_used,
            "rows": rows,
            "width": sheet_width,
            "height": sheet_height,
            "cell_width": cell_width,
            "gap": _GAP,
            "padding": _PADDING,
            "label_height": _LABEL_HEIGHT,
            "label_font_size": _LABEL_FONT_SIZE,
            "minimum_cell_width": _MIN_CELL_WIDTH,
            "source_image_scaling": "none",
        },
        "frames": frames,
        "authority": {
            "source_images": "embedded-byte-for-byte",
            "composition": "presentation-only",
            "raster_truth": "unchanged",
            "perceptual": "not-included",
        },
    }
    return StageContactSheet(manifest=manifest, svg=svg)


def write_stage_contact_sheet(
    sheet: StageContactSheet,
    output_dir: str | Path,
) -> None:
    """Materialize one complete contact sheet without mixing stale files."""

    root = Path(output_dir)
    if root.exists():
        if not root.is_dir():
            _fail("output_not_directory", "$.output_dir", "must be a directory path")
        if any(root.iterdir()):
            _fail(
                "output_not_empty",
                "$.output_dir",
                "refusing to overwrite a non-empty directory",
            )
    else:
        root.mkdir(parents=True)

    (root / "stage-contact-sheet.svg").write_bytes(sheet.svg)
    (root / "manifest.json").write_bytes(_canonical_json_bytes(sheet.manifest))
