from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Sequence

from evidence.g8_h4 import retained_authoring as h4
from tracepixel.agent import AgentProviderUsage, CodexCliProvider

PREVIOUS_TECHNICAL_RUN_ID = 32111680356
MAX_PROVIDER_CALLS = 1
MAX_INPUT_TOKENS = 18_943
MAX_OUTPUT_TOKENS = 3_548

H5_REQUIRED_APPROVALS = (
    "anatomy",
    "pose_readability",
    "silhouette",
    "equipment_attachment",
    "material_readability",
    "identity",
    "pixel_cluster_quality",
)

RETRY_INSTRUCTION = (
    "G8-H5 one-shot on existing 32x32 PixelProgram/Canvas; set_pixels only. "
    "Reuse H1/H2 intent: clearly three-quarter-right, never front-attention symmetry; head/torso/pelvis coherent; "
    "both feet grounded; both arms and legs individually readable using negative-space gaps away from shoulder/hip "
    "attachments while the full raster stays one connected component. Right-hand pixels must visibly touch/overlap "
    "a short spear shaft in front; left hand clear. Head identity: asymmetric high side-plume changes native-1x "
    "silhouette. Materials: matte teal cloth versus warm dark-brown leather; cool gray metal spearhead may be a third "
    "read. Use coherent 2-4px clusters, broad forms, top-left light; avoid confetti, merged limb/torso blobs, edge "
    "contact, translucency and palette overflow. Deterministic QA is correctness only, never visual acceptance."
)


class _RetryProvider:
    def __init__(self, delegate: object) -> None:
        self.delegate = delegate
        self.requests: list[dict[str, object]] = []

    def propose(self, request, /):
        if self.requests:
            raise RuntimeError("G8-H5 forbids provider repair/retry calls")
        transformed = copy.deepcopy(request)
        original_instruction = transformed.get("instruction", "")
        marker = "BOUND_HUMANOID_CONTEXT="
        if type(original_instruction) is not str or marker not in original_instruction:
            raise RuntimeError("H5 retry requires the retained H1/H2 bound humanoid context")
        bound_context = original_instruction[original_instruction.index(marker):]
        transformed["instruction"] = f"{RETRY_INSTRUCTION} {bound_context}"
        self.requests.append(copy.deepcopy(transformed))
        return self.delegate.propose(transformed)

    def last_usage(self, /) -> AgentProviderUsage | None:
        method = getattr(self.delegate, "last_usage", None)
        usage = method() if callable(method) else None
        return usage if isinstance(usage, AgentProviderUsage) else None

    def environment(self, /):
        method = getattr(self.delegate, "environment", None)
        if callable(method):
            return method()
        return SimpleNamespace(version=None, auth_mode=None, model=None, reasoning_effort=None)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _cost_guard(complexity: dict[str, object]) -> dict[str, object]:
    observed = {
        "provider_calls": complexity.get("provider_calls"),
        "input_tokens": complexity.get("input_tokens"),
        "output_tokens": complexity.get("output_tokens"),
    }
    checks = {
        "provider_calls": type(observed["provider_calls"]) is int and observed["provider_calls"] <= MAX_PROVIDER_CALLS,
        "input_tokens": type(observed["input_tokens"]) is int and observed["input_tokens"] <= MAX_INPUT_TOKENS,
        "output_tokens": type(observed["output_tokens"]) is int and observed["output_tokens"] <= MAX_OUTPUT_TOKENS,
    }
    return {
        "baseline_run_id": PREVIOUS_TECHNICAL_RUN_ID,
        "ceilings": {
            "provider_calls": MAX_PROVIDER_CALLS,
            "input_tokens": MAX_INPUT_TOKENS,
            "output_tokens": MAX_OUTPUT_TOKENS,
        },
        "observed": observed,
        "checks": checks,
        "passed": all(checks.values()),
    }


def validate_owner_review(criteria: object) -> bool:
    if type(criteria) is not dict or frozenset(criteria) != frozenset(H5_REQUIRED_APPROVALS):
        return False
    return all(criteria[name] is True for name in H5_REQUIRED_APPROVALS)


def run_retry(output_root: Path, provider_factory, *, source_sha: str) -> dict[str, object]:
    wrappers: list[_RetryProvider] = []

    def wrapped_factory() -> object:
        wrapped = _RetryProvider(provider_factory())
        wrappers.append(wrapped)
        return wrapped

    old_budget = h4._LOOP_BUDGET
    h4._LOOP_BUDGET = {
        "schema": old_budget["schema"],
        "max_iterations": 1,
        "max_tool_calls": 1,
        "max_operations": old_budget["max_operations"],
        "max_pixel_edits": old_budget["max_pixel_edits"],
    }
    try:
        technical = h4.run_retained_authoring(output_root, wrapped_factory, source_sha=source_sha)
    finally:
        h4._LOOP_BUDGET = old_budget

    if len(wrappers) != 1:
        raise RuntimeError("expected exactly one H5 provider instance")
    _write_json(output_root / "provider-requests.json", {"records": wrappers[0].requests})
    _write_json(output_root / "technical-summary.json", technical)

    complexity = json.loads((output_root / "complexity.json").read_text(encoding="utf-8"))
    guard = _cost_guard(complexity)
    _write_json(output_root / "quality-per-cost-guard.json", guard)
    deterministic_green = technical.get("status") == "succeeded" and not complexity["deterministic_qa"]["final_findings"]
    eligible = deterministic_green and guard["passed"]

    summary = copy.deepcopy(technical)
    summary.update(
        {
            "child": "G8-H5-retry",
            "status": "awaiting-owner-review" if eligible else "failed",
            "technical_status": technical.get("status"),
            "owner_verdict": "pending",
            "product_quality_status": "pending-owner-review" if eligible else "not-eligible",
            "retry_of_run_id": PREVIOUS_TECHNICAL_RUN_ID,
            "h5_required_approvals": list(H5_REQUIRED_APPROVALS),
            "provider_repair_calls_allowed": 0,
            "max_provider_calls": 1,
            "deterministic_qa_is_visual_quality_success": False,
            "new_schema_or_contract_added": False,
            "new_raster_authority_added": False,
            "skeletal_or_ik_authority_added": False,
            "animation_advanced": False,
            "trace2d_integration_advanced": False,
        }
    )
    _write_json(output_root / "summary.json", summary)
    (output_root / "review-package" / "H5_REVIEW.md").write_text(
        "# G8-H5 owner review\n\n"
        "Deterministic QA green and the cost guard only make this reviewable; they never promote quality.\n\n"
        "Approve every item on the native PNG first, then the 8x preview: anatomy; pose readability; silhouette; "
        "equipment attachment; material readability; identity; pixel-cluster quality.\n\n"
        "Any missing/rejected item is REJECT. G9 and Trace2D remain blocked.\n",
        encoding="utf-8",
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args(argv)

    try:
        summary = run_retry(
            args.output,
            lambda: CodexCliProvider(timeout_seconds=h4.PROVIDER_TIMEOUT_SECONDS),
            source_sha=args.source_sha,
        )
    except (Exception, SystemExit) as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        _write_json(
            args.output / "failure.json",
            {
                "child": "G8-H5-retry",
                "status": "failed",
                "source_sha": args.source_sha.lower(),
                "failure_type": type(exc).__name__,
                "message": str(exc),
                "new_schema_or_contract_added": False,
                "new_raster_authority_added": False,
                "provider_repair_calls_allowed": 0,
                "animation_advanced": False,
                "trace2d_integration_advanced": False,
            },
        )
        return 1

    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if summary["status"] == "awaiting-owner-review" else 2


if __name__ == "__main__":
    raise SystemExit(main())
