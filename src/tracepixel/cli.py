from __future__ import annotations

import argparse
import json
import platform
import sys
from typing import Sequence

from tracepixel import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tracepixel")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Emit deterministic local capability metadata.")
    return parser


def _doctor_payload() -> dict[str, object]:
    return {
        "schema": "tracepixel.doctor.v1",
        "tracepixel_version": __version__,
        "python": {
            "implementation": platform.python_implementation(),
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
        },
        "capabilities": {
            "core_package": True,
            "live_provider_required": False,
            "gpu_required": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        print(json.dumps(_doctor_payload(), sort_keys=True, separators=(",", ":")))
        return 0

    parser.print_help()
    return 0
