from __future__ import annotations

import binascii
import hashlib
import struct
import unittest
import zlib

from tracepixel.raster import (
    Canvas,
    CanvasSizeError,
    ExportScaleError,
    export_native_png,
    export_nearest_preview_png,
)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _decode_png_rgba8(png: bytes) -> tuple[int, int, bytes]:
    if not png.startswith(_PNG_SIGNATURE):
        raise AssertionError("missing PNG signature")

    offset = len(_PNG_SIGNATURE)
    ihdr: bytes | None = None
    idat_parts: list[bytes] = []
    saw_iend = False
    while offset < len(png):
        length = struct.unpack(">I", png[offset : offset + 4])[0]
        chunk_type = png[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        data = png[data_start:data_end]
        expected_crc = struct.unpack(">I", png[data_end : data_end + 4])[0]
        actual_crc = binascii.crc32(data, binascii.crc32(chunk_type)) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise AssertionError(f"invalid CRC for {chunk_type!r}")
        offset = data_end + 4

        if chunk_type == b"IHDR":
            ihdr = data
        elif chunk_type == b"IDAT":
            idat_parts.append(data)
        elif chunk_type == b"IEND":
            saw_iend = True
            break

    if ihdr is None or not saw_iend:
        raise AssertionError("incomplete PNG")
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", ihdr
    )
    if (bit_depth, color_type, compression, filter_method, interlace) != (8, 6, 0, 0, 0):
        raise AssertionError("unexpected PNG format")

    raw = zlib.decompress(b"".join(idat_parts))
    stride = width * 4
    expected_raw_length = height * (stride + 1)
    if len(raw) != expected_raw_length:
        raise AssertionError("unexpected raw scanline length")

    rgba = bytearray(width * height * 4)
    source = 0
    target = 0
    for _ in range(height):
        if raw[source] != 0:
            raise AssertionError("TracePixel export must use PNG filter 0")
        source += 1
        rgba[target : target + stride] = raw[source : source + stride]
        source += stride
        target += stride
    return width, height, bytes(rgba)


class PngExportTests(unittest.TestCase):
    def test_native_png_round_trips_exact_authoritative_rgba(self) -> None:
        canvas = Canvas(2, 2)
        canvas.set_pixels(
            [
                (0, 0, (255, 0, 0, 255)),
                (1, 0, (0, 255, 0, 128)),
                (0, 1, (0, 0, 255, 0)),
                (1, 1, (12, 34, 56, 78)),
            ]
        )
        expected = canvas.rgba_bytes()

        result = export_native_png(canvas)
        width, height, decoded = _decode_png_rgba8(result.png)

        self.assertEqual((width, height), (2, 2))
        self.assertEqual(decoded, expected)
        self.assertEqual(canvas.rgba_bytes(), expected)
        self.assertEqual(result.metadata.kind, "native")
        self.assertEqual(result.metadata.scale, 1)
        self.assertEqual(result.metadata.resampling, "none")
        self.assertEqual(result.metadata.filter, "none")
        self.assertEqual(result.metadata.compression, "deflate-stored")
        self.assertEqual(result.metadata.encoder, "tracepixel.png.rgba8.store.v1")
        self.assertEqual(
            result.metadata.authoritative_rgba_sha256,
            hashlib.sha256(expected).hexdigest(),
        )
        self.assertEqual(result.metadata.png_sha256, hashlib.sha256(result.png).hexdigest())
        self.assertEqual(result.metadata.as_dict()["width"], 2)

    def test_native_png_bytes_are_repeatable_for_encoder_v1(self) -> None:
        canvas = Canvas(2, 1)
        canvas.set_pixels(
            [
                (0, 0, (1, 2, 3, 4)),
                (1, 0, (250, 251, 252, 253)),
            ]
        )

        first = export_native_png(canvas)
        second = export_native_png(canvas)

        self.assertEqual(first, second)
        self.assertEqual(
            first.metadata.png_sha256,
            "c0374c8e9b62d101a1b188d9c043fe267a2b9641a172650e64c747bc53a207d5",
        )

    def test_nearest_preview_replicates_exact_pixels_without_antialiasing(self) -> None:
        canvas = Canvas(2, 1)
        left = (10, 20, 30, 40)
        right = (200, 210, 220, 230)
        canvas.set_pixels([(0, 0, left), (1, 0, right)])

        result = export_nearest_preview_png(canvas, scale=3)
        width, height, decoded = _decode_png_rgba8(result.png)

        expected_row = bytes(left * 3 + right * 3)
        self.assertEqual((width, height), (6, 3))
        self.assertEqual(decoded, expected_row * 3)
        self.assertEqual(result.metadata.kind, "nearest-preview")
        self.assertEqual(result.metadata.scale, 3)
        self.assertEqual(result.metadata.resampling, "nearest-neighbor")
        self.assertEqual((result.metadata.width, result.metadata.height), (6, 3))
        self.assertEqual((result.metadata.source_width, result.metadata.source_height), (2, 1))

    def test_preview_scale_requires_exact_integer_enlargement(self) -> None:
        canvas = Canvas(1, 1)
        for scale in (0, 1, -1, True, 2.0, "2"):
            with self.subTest(scale=scale):
                with self.assertRaises(ExportScaleError):
                    export_nearest_preview_png(canvas, scale=scale)  # type: ignore[arg-type]

    def test_preview_output_reuses_canvas_safety_ceiling(self) -> None:
        canvas = Canvas(4096, 1)

        with self.assertRaises(CanvasSizeError):
            export_nearest_preview_png(canvas, scale=2)


if __name__ == "__main__":
    unittest.main()
