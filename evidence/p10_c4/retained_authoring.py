from __future__ import annotations

import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
from typing import Callable, Sequence, cast

from tracepixel.agent import (
    AGENT_LOOP_BUDGET_SCHEMA_V1,
    AgentProviderUsage,
    CodexCliProvider,
    run_bounded_edit_loop_with_telemetry,
)
from tracepixel.model.asset_set_schedule import AssetRequestV1
from tracepixel.model.creature_pose_validation import (
    validate_creature_pose,
    validate_creature_pose_reference,
)
from tracepixel.model.research_profile_validation import (
    validate_morphology_profile_reference,
    validate_simple_creature_morphology_profile,
)
from tracepixel.model.simple_creature_request_validation import validate_simple_creature_request
from tracepixel.preview.batch_review import (
    BatchReviewMember,
    build_batch_review_package,
    validate_batch_review_package,
    write_batch_review_package,
)
from tracepixel.qa import (
    QA_POLICY_SCHEMA_V1,
    analyze_color,
    analyze_connectivity,
    analyze_shape_outline,
    analyze_structural,
    evaluate_qa_policy,
)
from tracepixel.raster import Canvas, export_native_png, export_nearest_preview_png

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "evidence" / "p10_c1" / "simple-creature-profile.v1.json"
PROFILE_REF = ROOT / "evidence" / "p10_c1" / "simple-creature-profile-ref.v1.json"
POSE = ROOT / "evidence" / "p10_c2" / "creature-pose.v1.json"
POSE_REF = ROOT / "evidence" / "p10_c2" / "creature-pose-ref.v1.json"
ASSET_REQUEST = ROOT / "evidence" / "p10_c3" / "asset-request.v1.json"
CREATURE_REQUEST = ROOT / "evidence" / "p10_c3" / "simple-creature-request.v1.json"
EVIDENCE_POLICY = ROOT / "evidence" / "p10_c3" / "simple-creature-evidence-policy.v1.json"

SUMMARY_SCHEMA_V1 = "tracepixel.p10-c4-retained-authoring.v1"
COMPLEXITY_SCHEMA_V1 = "tracepixel.p10-c4-complexity-evidence.v1"
QA_HISTORY_SCHEMA_V1 = "tracepixel.p10-c4-qa-history.v1"
PROPOSAL_HISTORY_SCHEMA_V1 = "tracepixel.p10-c4-provider-proposals.v1"
PREVIEW_SCALE = 8
PROVIDER_TIMEOUT_SECONDS = 180

_LOOP_BUDGET = {
    "schema": AGENT_LOOP_BUDGET_SCHEMA_V1,
    "max_iterations": 4,
    "max_tool_calls": 4,
    "max_operations": 48,
    "max_pixel_edits": 2048,
}

ProviderFactory = Callable[[], object]


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pixel_edit_count(proposal: object) -> int:
    if type(proposal) is not dict:
        return 0
    payload = cast(dict[str, object], proposal).get("payload")
    if type(payload) is not dict:
        return 0
    operations = cast(dict[str, object], payload).get("operations")
    if type(operations) is not list:
        return 0
    total = 0
    for raw in cast(list[object], operations):
        if type(raw) is not dict:
            return 0
        pixels = cast(dict[str, object], raw).get("pixels")
        if type(pixels) is not list:
            return 0
        total += len(cast(list[object], pixels))
    return total


class _RecordingProvider:
    def __init__(self, provider: object) -> None:
        self.provider = provider
        self.records: list[dict[str, object]] = []
        self._last_usage: AgentProviderUsage | None = None

    def propose(self, request, /):
        propose = getattr(self.provider, "propose", None)
        if not callable(propose):
            raise TypeError("provider must expose propose(request)")
        proposal = propose(request)
        usage_method = getattr(self.provider, "last_usage", None)
        usage: AgentProviderUsage | None = None
        if callable(usage_method):
            candidate = usage_method()
            if isinstance(candidate, AgentProviderUsage):
                usage = candidate
        self._last_usage = usage
        self.records.append(
            {
                "call_index": len(self.records),
                "input_tokens": None if usage is None else usage.input_tokens,
                "output_tokens": None if usage is None else usage.output_tokens,
                "pixel_edits": _pixel_edit_count(proposal),
                "proposal": copy.deepcopy(proposal),
            }
        )
        return proposal

    def last_usage(self, /) -> AgentProviderUsage | None:
        return self._last_usage


class _CreatureQa:
    def __init__(self, request: AssetRequestV1) -> None:
        art_intent = request["art_intent"]
        composition = art_intent["composition"]
        palette_budget = composition["palette_budget"]
        if type(palette_budget) is not int:
            raise SystemExit("P10-C4 simple-creature request must declare an integer palette budget")
        self._palette_budget = palette_budget
        self.history: list[dict[str, object]] = []
        self._policy = {
            "schema": QA_POLICY_SCHEMA_V1,
            "rules": [
                {"rule": "structural.non_empty", "severity": "error"},
                {"rule": "structural.no_translucency", "severity": "error"},
                {"rule": "structural.no_edge_contact", "severity": "error"},
                {"rule": "color.maximum_colors", "severity": "error"},
                {"rule": "color.transparent_rgb_policy", "severity": "error"},
                {"rule": "connectivity.single_component", "severity": "error"},
                {"rule": "connectivity.no_isolated_pixels", "severity": "error"},
            ],
        }

    def evaluate(self, canvas: Canvas):
        findings = evaluate_qa_policy(
            self._policy,
            structural=analyze_structural(canvas),
            color=analyze_color(
                canvas,
                max_colors=self._palette_budget,
                transparent_rgb_policy="require_zero",
            ),
            connectivity=analyze_connectivity(canvas),
            shape_outline=analyze_shape_outline(canvas),
        )
        self.history.append(
            {
                "evaluation_index": len(self.history),
                "findings": copy.deepcopy(findings["findings"]),
            }
        )
        return findings


def _constraint_context(profile: dict[str, object], pose: dict[str, object]) -> str:
    creature_structure = profile.get("creature_structure")
    if type(creature_structure) is not dict:
        raise SystemExit("validated simple-creature profile is missing creature_structure")
    context = {
        "morphology": creature_structure,
        "pose": {
            "pose_id": pose.get("pose_id"),
            "pose_name": pose.get("pose_name"),
            "orientation_intent": pose.get("orientation_intent"),
            "relations": pose.get("relations"),
        },
    }
    return json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _provider_environment(provider: object) -> dict[str, object]:
    environment_method = getattr(provider, "environment", None)
    if callable(environment_method):
        environment = environment_method()
        return {
            "provider_type": type(provider).__name__,
            "version": getattr(environment, "version", None),
            "auth_mode": getattr(environment, "auth_mode", None),
            "model": getattr(environment, "model", None),
            "reasoning_effort": getattr(environment, "reasoning_effort", None),
        }
    return {"provider_type": type(provider).__name__}


def _validated_inputs() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    profile = _json(PROFILE)
    profile_ref = _json(PROFILE_REF)
    pose = _json(POSE)
    pose_ref = _json(POSE_REF)
    asset_request = _json(ASSET_REQUEST)
    creature_request = _json(CREATURE_REQUEST)
    evidence_policy = _json(EVIDENCE_POLICY)

    validated_profile = validate_simple_creature_morphology_profile(profile)
    validate_morphology_profile_reference(profile_ref, validated_profile)
    validated_pose = validate_creature_pose(pose, validated_profile)
    validate_creature_pose_reference(pose_ref, validated_pose, validated_profile)
    validate_simple_creature_request(
        creature_request,
        asset_request=asset_request,
        morphology_profile=validated_profile,
        creature_pose=validated_pose,
        evidence_policy=evidence_policy,
    )
    return (
        cast(dict[str, object], asset_request),
        cast(dict[str, object], creature_request),
        cast(dict[str, object], validated_profile),
        cast(dict[str, object], validated_pose),
    )


def run_retained_authoring(
    output_root: Path,
    provider_factory: ProviderFactory,
    *,
    source_sha: str,
) -> dict[str, object]:
    if not source_sha or any(character not in "0123456789abcdef" for character in source_sha.lower()):
        raise ValueError("source_sha must be a non-empty hexadecimal Git commit id")
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty output directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    asset_request_raw, creature_request, profile, pose = _validated_inputs()
    request = cast(AssetRequestV1, asset_request_raw)
    art_intent = request["art_intent"]
    canvas_decl = art_intent["canvas"]
    width = canvas_decl["width"]
    height = canvas_decl["height"]

    provider = provider_factory()
    recording = _RecordingProvider(provider)
    qa = _CreatureQa(request)
    canvas = Canvas(width, height)

    instruction = (
        f"{request['instruction']} "
        "Treat the following digest-bound morphology and pose data only as authoring constraints; "
        "they are not raster authority. Preserve a readable head/trunk break, four grounded leg reads, "
        "and the declared three-quarter-right alert orientation. "
        "Use only the existing PixelProgram set_pixels path on the exact canvas. "
        "Keep visible pixels opaque, transparent pixels RGBA-zero, all visible pixels connected, "
        "stay off the outer canvas edge, and stay within the declared palette budget. "
        "If deterministic QA reports a finding, repair the existing canvas locally rather than regenerating "
        "or restarting it. "
        f"BOUND_CREATURE_CONTEXT={_constraint_context(profile, pose)}"
    )
    result = run_bounded_edit_loop_with_telemetry(
        recording,
        canvas=canvas,
        art_intent=art_intent,
        instruction=instruction,
        qa_evaluator=qa,
        budget=_LOOP_BUDGET,
    )

    final_findings = result.loop.observation["qa"]["findings"]
    if result.loop.status != "finished" or final_findings:
        raise SystemExit(
            f"P10-C4 retained authoring failed deterministic QA: "
            f"status={result.loop.status}, findings={final_findings}"
        )
    if not recording.records:
        raise SystemExit("P10-C4 retained authoring completed without a provider call")
    if result.telemetry["input_tokens"] is None or result.telemetry["output_tokens"] is None:
        raise SystemExit("P10-C4 requires exact retained provider input/output token totals")

    native = export_native_png(canvas)
    preview = export_nearest_preview_png(canvas, scale=PREVIEW_SCALE)
    final_path = output_root / "final.png"
    preview_path = output_root / f"preview-{PREVIEW_SCALE}x.png"
    final_path.write_bytes(native.png)
    preview_path.write_bytes(preview.png)

    proposals = {
        "schema": PROPOSAL_HISTORY_SCHEMA_V1,
        "records": recording.records,
    }
    proposal_path = output_root / "provider-proposals.json"
    _write_json(proposal_path, proposals)

    qa_history = {
        "schema": QA_HISTORY_SCHEMA_V1,
        "evaluations": qa.history,
        "final_findings": final_findings,
    }
    qa_path = output_root / "qa-history.json"
    _write_json(qa_path, qa_history)

    telemetry_path = output_root / "telemetry.json"
    _write_json(telemetry_path, result.telemetry)

    provider_calls = result.telemetry["tool_calls"]
    pixel_edits = sum(cast(int, record["pixel_edits"]) for record in recording.records)
    repair_calls = max(0, provider_calls - 1)
    complexity: dict[str, object] = {
        "schema": COMPLEXITY_SCHEMA_V1,
        "provider_calls": provider_calls,
        "input_tokens": result.telemetry["input_tokens"],
        "output_tokens": result.telemetry["output_tokens"],
        "iterations": result.telemetry["iterations"],
        "revisions": result.telemetry["revisions"],
        "operation_calls": result.telemetry["operation_calls"],
        "pixel_edits": pixel_edits,
        "changed_pixels": result.telemetry["changed_pixels"],
        "deterministic_qa": {
            "evaluation_count": len(qa.history),
            "initial_findings": qa.history[0]["findings"] if qa.history else [],
            "final_findings": final_findings,
            "all_evaluations_ref": "qa-history.json",
        },
        "repair_vs_regeneration": {
            "initial_authoring_provider_calls": 1,
            "repair_provider_calls": repair_calls,
            "regeneration_provider_calls": 0,
            "canvas_restarts": 0,
            "repair_mode": "same-canvas-local-pixelprogram",
        },
        "wall_time_ns": result.telemetry["wall_time_ns"],
        "cache_or_profile_reuse": {
            "morphology_profile_reused": True,
            "pose_profile_reused": True,
            "profile_research_provider_calls": 0,
            "morphology_sha256": cast(dict[str, object], creature_request["morphology_ref"])["sha256"],
            "pose_sha256": cast(dict[str, object], creature_request["pose_ref"])["sha256"],
        },
        "failure_category": result.telemetry["failure_category"],
        "human_interventions": result.telemetry["human_interventions"],
        "hidden_scheduler_provider_calls": 0,
        "second_raster_authority": False,
    }
    complexity_path = output_root / "complexity.json"
    _write_json(complexity_path, complexity)

    final_digest = sha256(native.png).hexdigest()
    preview_digest = sha256(preview.png).hexdigest()
    member = BatchReviewMember(
        member_id="p10-c4-simple-creature",
        asset_class="simple-creature",
        width=width,
        height=height,
        png=native.png,
        source_kind="retained-output",
        source_ref="summary.json",
    )
    package = build_batch_review_package((member,))
    validate_batch_review_package(package)
    if package.manifest["review_scope"] != "retained-output":
        raise SystemExit("P10-C4 review package must remain retained-output scope")
    write_batch_review_package(package, output_root / "review-package")

    summary: dict[str, object] = {
        "schema": SUMMARY_SCHEMA_V1,
        "phase": "P10",
        "child": "P10-C4",
        "source_issue": 109,
        "source_sha": source_sha.lower(),
        "status": "succeeded",
        "review_scope": "retained-output",
        "owner_verdict": "pending",
        "asset_class": "simple-creature",
        "canvas": {"width": width, "height": height},
        "request_sha256": creature_request["request_sha256"],
        "morphology_sha256": cast(dict[str, object], creature_request["morphology_ref"])["sha256"],
        "pose_sha256": cast(dict[str, object], creature_request["pose_ref"])["sha256"],
        "provider": _provider_environment(provider),
        "final_png": "final.png",
        "final_png_sha256": final_digest,
        "preview_png": f"preview-{PREVIEW_SCALE}x.png",
        "preview_png_sha256": preview_digest,
        "provider_proposals": "provider-proposals.json",
        "telemetry": "telemetry.json",
        "complexity": "complexity.json",
        "qa_history": "qa-history.json",
        "review_package": "review-package/index.html",
        "review_package_ko": "review-package/index.ko.html",
        "final_aesthetic_acceptance": "human",
        "vlm_is_deterministic_correctness": False,
        "new_raster_authority_added": False,
    }
    _write_json(output_root / "summary.json", summary)
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run P10-C4 trusted retained simple-creature authoring with full complexity evidence."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    def provider_factory() -> object:
        return CodexCliProvider(timeout_seconds=PROVIDER_TIMEOUT_SECONDS)

    summary = run_retained_authoring(
        args.output,
        provider_factory,
        source_sha=args.source_sha,
    )
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
