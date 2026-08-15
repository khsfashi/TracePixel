from __future__ import annotations

import argparse
import gc
import json
import platform
import statistics
import struct
import sys
import time
import tracemalloc
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeVar

from tracepixel.raster import Canvas, export_native_png, export_nearest_preview_png

SIZES = (16, 32, 64)
PREVIEW_SCALE = 2
REPORT_SCHEMA = "tracepixel.p1-r4-runtime-evidence.v1"
STRUCTURAL_SCHEMA = "tracepixel.p1-r4-structural-evidence.v1"

_T = TypeVar("_T")


def _fixture_edits(size: int) -> tuple[tuple[int, int, tuple[int, int, int, int]], ...]:
    return tuple(
        (
            x,
            y,
            (
                (x * 17 + y * 13) & 0xFF,
                (x * 7 + y * 29) & 0xFF,
                (x * 31 + y * 3) & 0xFF,
                255,
            ),
        )
        for y in range(size)
        for x in range(size)
    )


def _render(size: int, edits: Sequence[tuple[int, int, tuple[int, int, int, int]]]) -> Canvas:
    canvas = Canvas(size, size)
    canvas.set_pixels(edits)
    return canvas


def build_structural_case(size: int) -> dict[str, object]:
    edits = _fixture_edits(size)
    canvas = _render(size, edits)
    snapshot = canvas.rgba_bytes()
    native = export_native_png(canvas)
    preview = export_nearest_preview_png(canvas, scale=PREVIEW_SCALE)

    return {
        "size": size,
        "full_batch_edit_count": len(edits),
        "authoritative_storage_payload_bytes": canvas.byte_length,
        "explicit_owned_snapshot_payload_bytes": len(snapshot),
        "native_png_payload_bytes": len(native.png),
        "preview_scale": PREVIEW_SCALE,
        "preview_width": preview.metadata.width,
        "preview_height": preview.metadata.height,
        "preview_raster_payload_bytes": preview.metadata.width
        * preview.metadata.height
        * 4,
        "preview_row_buffer_payload_bytes": preview.metadata.width * 4,
        "preview_png_payload_bytes": len(preview.png),
    }


def build_structural_evidence() -> dict[str, object]:
    return {
        "schema": STRUCTURAL_SCHEMA,
        "notes": {
            "authoritative_storage": "one owned contiguous row-major RGBA8 bytearray",
            "snapshot": "full RGBA copy exists only when rgba_bytes() ownership is explicitly requested",
            "native_export": "encoder borrows a read-only source view; returned PNG bytes are derived output",
            "preview_export": "no full preview canvas is materialized; one scaled row buffer is reused",
            "batch_mutation": "transactional full-batch validation uses temporary O(edit_count) Python staging",
        },
        "cases": [build_structural_case(size) for size in SIZES],
    }


def _measure_allocation(action: Callable[[], _T]) -> tuple[_T, dict[str, int]]:
    gc.collect()
    tracemalloc.start()
    try:
        baseline_current, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        result = action()
        current, peak = tracemalloc.get_traced_memory()
        return result, {
            "retained_extra_bytes": max(0, current - baseline_current),
            "peak_extra_bytes": max(0, peak - baseline_current),
        }
    finally:
        tracemalloc.stop()


def _measure_timing(action: Callable[[], object], iterations: int) -> dict[str, int]:
    if type(iterations) is not int or iterations < 1:
        raise ValueError("iterations must be an exact integer >= 1")

    for _ in range(min(3, iterations)):
        action()

    samples: list[int] = []
    gc_was_enabled = gc.isenabled()
    if gc_was_enabled:
        gc.disable()
    try:
        for _ in range(iterations):
            start = time.perf_counter_ns()
            action()
            samples.append(time.perf_counter_ns() - start)
    finally:
        if gc_was_enabled:
            gc.enable()

    return {
        "iterations": iterations,
        "min_ns": min(samples),
        "median_ns": int(statistics.median(samples)),
        "max_ns": max(samples),
    }


def collect_runtime_case(size: int, *, iterations: int) -> dict[str, object]:
    edits = _fixture_edits(size)
    canvas = _render(size, edits)

    mutation_canvas = Canvas(size, size)
    _, set_pixel_allocation = _measure_allocation(
        lambda: mutation_canvas.set_pixel(0, 0, (1, 2, 3, 4))
    )

    batch_canvas = Canvas(size, size)
    _, set_pixels_allocation = _measure_allocation(lambda: batch_canvas.set_pixels(edits))

    snapshot, snapshot_allocation = _measure_allocation(canvas.rgba_bytes)
    native, native_allocation = _measure_allocation(lambda: export_native_png(canvas))
    preview, preview_allocation = _measure_allocation(
        lambda: export_nearest_preview_png(canvas, scale=PREVIEW_SCALE)
    )

    def replay_once() -> None:
        _render(size, edits)

    return {
        "size": size,
        "allocation": {
            "set_pixel": set_pixel_allocation,
            "set_pixels_full_canvas": set_pixels_allocation,
            "rgba_snapshot": {
                **snapshot_allocation,
                "payload_bytes": len(snapshot),
            },
            "native_export": {
                **native_allocation,
                "output_payload_bytes": len(native.png),
            },
            "preview_export": {
                **preview_allocation,
                "output_payload_bytes": len(preview.png),
            },
        },
        "timing": {
            "replay": _measure_timing(replay_once, iterations),
            "native_export": _measure_timing(lambda: export_native_png(canvas), iterations),
            "preview_export": _measure_timing(
                lambda: export_nearest_preview_png(canvas, scale=PREVIEW_SCALE),
                iterations,
            ),
        },
    }


def _environment() -> dict[str, object]:
    clock = time.get_clock_info("perf_counter")
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "pointer_bits": struct.calcsize("P") * 8,
        "byteorder": sys.byteorder,
        "allocation_probe": "tracemalloc",
        "timing_clock": "perf_counter_ns",
        "timing_clock_resolution_seconds": clock.resolution,
        "timing_clock_monotonic": clock.monotonic,
    }


def build_runtime_report(*, iterations: int) -> dict[str, object]:
    return {
        "schema": REPORT_SCHEMA,
        "scope": "engineering-microbenchmark-not-portable-performance-claim",
        "preview_scale": PREVIEW_SCALE,
        "environment": _environment(),
        "structural": build_structural_evidence(),
        "runtime_cases": [
            collect_runtime_case(size, iterations=iterations) for size in SIZES
        ],
    }


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect TracePixel P1-R4 raster evidence.")
    parser.add_argument(
        "--iterations",
        type=int,
        default=7,
        help="timed iterations per operation and canvas size (default: 7)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON output path; stdout is always emitted",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_runtime_report(iterations=args.iterations)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
