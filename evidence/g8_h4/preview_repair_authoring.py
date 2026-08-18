from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

from evidence.g8_h4 import retained_authoring as base
from tracepixel.agent import AgentPreviewFrame, CodexCliProvider
from tracepixel.raster import Canvas, export_nearest_preview_png

REPAIR_PREVIEW_SCALE = 2

_REPAIR_GUIDANCE = (
    " Repair guidance for this H4 retained run: every provider request with deterministic QA findings includes a current-canvas PNG preview. "
    "The palette budget is exactly 16 visible RGBA colors. If color.maximum_colors is present, preserve the existing drawing and remap/reuse colors already on the canvas; do not introduce new colors. "
    "If connectivity.single_component or connectivity.no_isolated_pixels is present, inspect the current preview and connect a tiny detached spear/highlight/body pixel to adjacent opaque pixels or clear only the detached pixels. "
    "Do not redraw the whole sprite to fix a local finding. Preserve already-good pixels, anatomy, pose, spear placement, and silhouette, and touch only pixels needed for remaining deterministic findings."
)


class _CurrentCanvasPreview:
    """Read-only provider observation of the existing authoritative Canvas."""

    def observe(self, canvas: Canvas, /) -> AgentPreviewFrame:
        preview = export_nearest_preview_png(canvas, scale=REPAIR_PREVIEW_SCALE)
        return AgentPreviewFrame(
            png=preview.png,
            width=preview.metadata.width,
            height=preview.metadata.height,
        )


def run_preview_repair_authoring(
    output_root: Path,
    provider_factory: Callable[[], object],
    *,
    source_sha: str,
) -> dict[str, object]:
    """Reuse H4 authoring while enabling the existing bounded preview-observation seam."""

    original_loop = base.run_bounded_edit_loop_with_telemetry

    def loop_with_preview(provider, /, **kwargs):
        instruction = kwargs.get("instruction")
        if type(instruction) is not str:
            raise TypeError("H4 preview repair requires a string authoring instruction")
        if kwargs.get("preview_observer") is not None:
            raise RuntimeError("H4 preview repair refuses a second preview observer")
        kwargs["instruction"] = instruction + _REPAIR_GUIDANCE
        kwargs["preview_observer"] = _CurrentCanvasPreview()
        return original_loop(provider, **kwargs)

    base.run_bounded_edit_loop_with_telemetry = loop_with_preview
    try:
        return base.run_retained_authoring(
            output_root,
            provider_factory,
            source_sha=source_sha,
        )
    finally:
        base.run_bounded_edit_loop_with_telemetry = original_loop


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run G8-H4 retained authoring with current-canvas preview feedback for bounded local repairs."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    def provider_factory() -> object:
        return CodexCliProvider(timeout_seconds=base.PROVIDER_TIMEOUT_SECONDS)

    try:
        summary = run_preview_repair_authoring(
            args.output,
            provider_factory,
            source_sha=args.source_sha,
        )
    except (Exception, SystemExit) as exc:
        base._write_early_failure(args.output, args.source_sha, exc)
        print(json.dumps({"status": "failed", "failure": str(exc)}, sort_keys=True))
        return 1

    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0 if summary["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
