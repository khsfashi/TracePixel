from __future__ import annotations

import binascii
import hashlib
import struct
import zlib
from dataclasses import dataclass

from tracepixel.raster.canvas import Canvas
from tracepixel.raster.contract import BYTES_PER_PIXEL, CanvasSpec, RasterContractError

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_ENCODER = "tracepixel.png.rgba8.store.v1"
_MAX_DEFLATE_STORED_BLOCK = 65535
_FILTER_NONE = b"\x00"


class ExportScaleError(RasterContractError):
    """Raised when an enlarged preview scale is not a valid exact integer."""


@dataclass(frozen=True, slots=True)
class PngExportMetadata:
    schema: str
    kind: str
    source_width: int
    source_height: int
    width: int
    height: int
    scale: int
    pixel_format: str
    alpha_mode: str
    resampling: str
    filter: str
    compression: str
    encoder: str
    authoritative_rgba_sha256: str
    png_sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "kind": self.kind,
            "source_width": self.source_width,
            "source_height": self.source_height,
            "width": self.width,
            "height": self.height,
            "scale": self.scale,
            "pixel_format": self.pixel_format,
            "alpha_mode": self.alpha_mode,
            "resampling": self.resampling,
            "filter": self.filter,
            "compression": self.compression,
            "encoder": self.encoder,
            "authoritative_rgba_sha256": self.authoritative_rgba_sha256,
            "png_sha256": self.png_sha256,
        }


@dataclass(frozen=True, slots=True)
class PngExport:
    png: bytes
    metadata: PngExportMetadata


def export_native_png(canvas: Canvas) -> PngExport:
    """Encode the exact authoritative canvas as deterministic RGBA8 PNG bytes."""
    return _export_png(canvas, scale=1, kind="native", resampling="none")


def export_nearest_preview_png(canvas: Canvas, scale: int = 8) -> PngExport:
    """Encode an enlarged nearest-neighbor preview without changing source pixels."""
    if type(scale) is not int or scale < 2:
        raise ExportScaleError("preview scale must be an exact integer >= 2")
    CanvasSpec(canvas.width * scale, canvas.height * scale)
    return _export_png(
        canvas,
        scale=scale,
        kind="nearest-preview",
        resampling="nearest-neighbor",
    )


def _export_png(canvas: Canvas, *, scale: int, kind: str, resampling: str) -> PngExport:
    source = canvas._rgba_view()
    width = canvas.width * scale
    height = canvas.height * scale
    authoritative_digest = hashlib.sha256(source).hexdigest()
    png = _encode_rgba8_png(source, canvas.width, canvas.height, scale)
    metadata = PngExportMetadata(
        schema="tracepixel.png-export.v1",
        kind=kind,
        source_width=canvas.width,
        source_height=canvas.height,
        width=width,
        height=height,
        scale=scale,
        pixel_format="RGBA8",
        alpha_mode="straight",
        resampling=resampling,
        filter="none",
        compression="deflate-stored",
        encoder=_PNG_ENCODER,
        authoritative_rgba_sha256=authoritative_digest,
        png_sha256=hashlib.sha256(png).hexdigest(),
    )
    return PngExport(png=png, metadata=metadata)


def _encode_rgba8_png(
    source: memoryview,
    source_width: int,
    source_height: int,
    scale: int,
) -> bytes:
    width = source_width * scale
    height = source_height * scale
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    stream = _StoredZlibStream()
    source_stride = source_width * BYTES_PER_PIXEL
    if scale == 1:
        for y in range(source_height):
            row_start = y * source_stride
            stream.write(_FILTER_NONE)
            stream.write(source[row_start : row_start + source_stride])
    else:
        scaled_row = bytearray(width * BYTES_PER_PIXEL)
        for y in range(source_height):
            row_start = y * source_stride
            _scale_row_nearest(source, row_start, source_width, scale, scaled_row)
            for _ in range(scale):
                stream.write(_FILTER_NONE)
                stream.write(scaled_row)

    idat = stream.finish()
    idat_crc = _crc32_parts(b"IDAT", idat)
    return b"".join(
        (
            _PNG_SIGNATURE,
            _png_chunk(b"IHDR", ihdr),
            struct.pack(">I", len(idat)),
            b"IDAT",
            idat,
            struct.pack(">I", idat_crc),
            _png_chunk(b"IEND", b""),
        )
    )


def _scale_row_nearest(
    source: memoryview,
    row_start: int,
    source_width: int,
    scale: int,
    target: bytearray,
) -> None:
    target_offset = 0
    for x in range(source_width):
        source_offset = row_start + x * BYTES_PER_PIXEL
        pixel = source[source_offset : source_offset + BYTES_PER_PIXEL]
        for _ in range(scale):
            target[target_offset : target_offset + BYTES_PER_PIXEL] = pixel
            target_offset += BYTES_PER_PIXEL


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = _crc32_parts(chunk_type, data)
    return b"".join(
        (
            struct.pack(">I", len(data)),
            chunk_type,
            data,
            struct.pack(">I", crc),
        )
    )


def _crc32_parts(first: bytes, second: bytes | bytearray) -> int:
    return binascii.crc32(second, binascii.crc32(first)) & 0xFFFFFFFF


class _StoredZlibStream:
    """Deterministic zlib stream using only RFC 1951 stored DEFLATE blocks."""

    __slots__ = ("_out", "_pending", "_adler32")

    def __init__(self) -> None:
        # CMF/FLG 0x78 0x01: deflate, 32 KiB window, no preset dictionary, FCHECK valid.
        self._out = bytearray((0x78, 0x01))
        self._pending = bytearray()
        self._adler32 = 1

    def write(self, data: bytes | bytearray | memoryview) -> None:
        if not data:
            return
        self._adler32 = zlib.adler32(data, self._adler32) & 0xFFFFFFFF
        self._pending.extend(data)
        while len(self._pending) > _MAX_DEFLATE_STORED_BLOCK:
            self._emit_block(_MAX_DEFLATE_STORED_BLOCK, final=False)

    def finish(self) -> bytearray:
        self._emit_block(len(self._pending), final=True)
        self._out.extend(struct.pack(">I", self._adler32))
        return self._out

    def _emit_block(self, length: int, *, final: bool) -> None:
        self._out.append(0x01 if final else 0x00)
        self._out.extend(struct.pack("<HH", length, length ^ 0xFFFF))
        if length:
            block = self._pending[:length]
            self._out.extend(block)
            del self._pending[:length]
