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
from tracepixel.model.humanoid_pose_validation import (
    validate_humanoid_pose,
    validate_humanoid_pose_reference,
)
from tracepixel.model.humanoid_profile_validation import (
    validate_humanoid_profile,
    validate_humanoid_profile_reference,
)
from tracepixel.model.static_humanoid_request_validation import validate_static_humanoid_request
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
PROFILE = ROOT / "evidence" / "g8_h1" / "humanoid-profile.v1.json"
PROFILE_REF = ROOT / "evidence" / "g8_h1" / "humanoid-profile-ref.v1.json"
POSE = ROOT / "evidence" / "g8_h2" / "humanoid-pose.v1.json"
POSE_REF = ROOT / "evidence" / "g8_h2" / "humanoid-pose-ref.v1.json"
ASSET_REQUEST = ROOT / "evidence" / "g8_h3" / "asset-request.v1.json"
HUMANOID_REQUEST = ROOT / "evidence" / "g8_h3" / "static-humanoid-request.v1.json"
EVIDENCE_POLICY = ROOT / "evidence" / "g8_h3" / "static-humanoid-evidence-policy.v1.json"

PREVIEW_SCALE = 8
PROVIDER_TIMEOUT_SECONDS = 180

_LOOP_BUDGET = {
    "schema": AGENT_LOOP_BUDGET_SCHEMA_V1,
    "max_iterations": 4,
    "max_tool_calls": 4,
    "max_operations": 48,
    "max_pixel_edits": 2048,
}

P10_C4_BASELINE = {
    "run_id": 32099831527,
    "artifact_id": 9311214420,
    "canvas": {"width": 32, "height": 32},
    "provider_calls": 1,
    "input_tokens": 18854,
    "output_tokens": 3762,
    "operation_calls": 1,
    "pixel_edits": 270,
    "changed_pixels": 270,
    "regeneration_provider_calls": 0,
}

ProviderFactory = Callable[[], object]


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _ratio(value: object, baseline: int) -> float | None:
    if type(value) is not int or baseline <= 0:
        return None
    return round(value / baseline, 4)


def _delta(value: object, baseline: int) -> int | None:
    if type(value) is not int:
        return None
    return value - baseline


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


class _HumanoidQa:
    def __init__(self, request: AssetRequestV1, stage_root: Path) -> None:
        art_intent = request["art_intent"]
        composition = art_intent["composition"]
        palette_budget = composition["palette_budget"]
        if type(palette_budget) is not int:
            raise SystemExit("G8-H4 static humanoid request must declare an integer palette budget")
        self._palette_budget = palette_budget
        self._stage_root = stage_root
        self.history: list[dict[str, object]] = []
        self.stages: list[dict[str, object]] = []
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
        stage_index = len(self.stages)
        native = export_native_png(canvas)
        preview = export_nearest_preview_png(canvas, scale=PREVIEW_SCALE)
        native_name = f"stage-{stage_index:02d}.png"
        preview_name = f"stage-{stage_index:02d}-{PREVIEW_SCALE}x.png"
        self._stage_root.mkdir(parents=True, exist_ok=True)
        (self._stage_root / native_name).write_bytes(native.png)
        (self._stage_root / preview_name).write_bytes(preview.png)

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
        finding_records = copy.deepcopy(findings["findings"])
        self.history.append(
            {
                "evaluation_index": len(self.history),
                "findings": finding_records,
            }
        )
        self.stages.append(
            {
                "stage_index": stage_index,
                "native_png": f"stages/{native_name}",
                "preview_png": f"stages/{preview_name}",
                "finding_count": len(finding_records),
                "semantic_stage_claimed": False,
                "meaning": "bounded-loop QA snapshot; not a new authoring-stage authority",
            }
        )
        return findings


def _constraint_context(
    humanoid_request: dict[str, object],
    profile: dict[str, object],
    pose: dict[str, object],
) -> str:
    context = {
        "bound_refs": {
            "profile_ref": humanoid_request.get("profile_ref"),
            "pose_ref": humanoid_request.get("pose_ref"),
        },
        "profile": {
            "identity": profile.get("identity"),
            "proportion_constraints": profile.get("proportion_constraints"),
            "identity_features": profile.get("identity_features"),
            "support_landmark_ids": profile.get("support_landmark_ids"),
            "equipment_anchors": profile.get("equipment_anchors"),
            "stylization_tolerance": profile.get("stylization_tolerance"),
        },
        "pose": {
            "pose_id": pose.get("pose_id"),
            "pose_name": pose.get("pose_name"),
            "orientation_intent": pose.get("orientation_intent"),
            "relations": pose.get("relations"),
            "equipment_attachments": pose.get("equipment_attachments"),
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
    humanoid_request = _json(HUMANOID_REQUEST)
    evidence_policy = _json(EVIDENCE_POLICY)

    validated_profile = validate_humanoid_profile(profile)
    validate_humanoid_profile_reference(profile_ref, validated_profile)
    validated_pose = validate_humanoid_pose(pose, validated_profile)
    validate_humanoid_pose_reference(pose_ref, validated_pose, validated_profile)
    validate_static_humanoid_request(
        humanoid_request,
        asset_request=asset_request,
        humanoid_profile=validated_profile,
        humanoid_pose=validated_pose,
        evidence_policy=evidence_policy,
    )
    return (
        cast(dict[str, object], asset_request),
        cast(dict[str, object], humanoid_request),
        cast(dict[str, object], validated_profile),
        cast(dict[str, object], validated_pose),
    )


def _comparison(complexity: dict[str, object]) -> dict[str, object]:
    comparisons: dict[str, object] = {}
    for field in (
        "provider_calls",
        "input_tokens",
        "output_tokens",
        "operation_calls",
        "pixel_edits",
        "changed_pixels",
    ):
        baseline = cast(int, P10_C4_BASELINE[field])
        value = complexity.get(field)
        comparisons[field] = {
            "p10_c4": baseline,
            "g8_h4": value,
            "delta": _delta(value, baseline),
            "multiplier": _ratio(value, baseline),
        }
    comparisons["wall_time"] = {
        "p10_c4": "not frozen in the public P10-C5 summary",
        "g8_h4_wall_time_ns": complexity.get("wall_time_ns"),
        "multiplier": None,
    }
    return {
        "baseline": "P10-C4 retained simple-creature run 32099831527 / artifact 9311214420",
        "baseline_facts": P10_C4_BASELINE,
        "metrics": comparisons,
    }


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

    asset_request_raw, humanoid_request, profile, pose = _validated_inputs()
    request = cast(AssetRequestV1, asset_request_raw)
    art_intent = request["art_intent"]
    canvas_decl = art_intent["canvas"]
    width = canvas_decl["width"]
    height = canvas_decl["height"]

    provider = provider_factory()
    recording = _RecordingProvider(provider)
    qa = _HumanoidQa(request, output_root / "stages")
    canvas = Canvas(width, height)

    instruction = (
        f"{request['instruction']} "
        "This is G8-H4 contract sufficiency validation, not schema design. "
        "Use the existing single-asset PixelProgram set_pixels path on the exact canvas and do not invent a skeleton, IK solve, physics pass, equipment renderer, hidden planner, or second raster authority. "
        "Render one readable compact humanoid adventurer in a grounded three-quarter-right guard pose. "
        "Make the head/face treatment, torso/pelvis grouping, two distinct grounded feet, and two hands readable at native 1x. "
        "The right-hand grip must visibly hold one short spear in front of the hand/torso overlap; the left hand must remain visibly free. "
        "Favor a strong silhouette and coarse anatomy over micro-detail. Preserve top-left lighting within the palette budget. "
        "Keep visible pixels opaque, transparent pixels RGBA-zero, all visible pixels connected, and stay off the outer canvas edge. "
        "If deterministic QA reports a finding, repair the existing canvas locally; do not regenerate or restart. "
        "Deterministic QA does not certify face quality, anatomy believability, pose readability, silhouette quality, equipment readability, or aesthetics; those remain for H5 human review. "
        f"BOUND_HUMANOID_CONTEXT={_constraint_context(humanoid_request, profile, pose)}"
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
    native = export_native_png(canvas)
    preview = export_nearest_preview_png(canvas, scale=PREVIEW_SCALE)
    final_path = output_root / "final.png"
    preview_path = output_root / f"preview-{PREVIEW_SCALE}x.png"
    final_path.write_bytes(native.png)
    preview_path.write_bytes(preview.png)

    _write_json(
        output_root / "provider-proposals.json",
        {"records": recording.records},
    )
    _write_json(
        output_root / "qa-history.json",
        {
            "evaluations": qa.history,
            "final_findings": final_findings,
        },
    )
    _write_json(output_root / "stage-index.json", {"stages": qa.stages})
    _write_json(output_root / "telemetry.json", result.telemetry)

    provider_calls = result.telemetry["tool_calls"]
    pixel_edits = sum(cast(int, record["pixel_edits"]) for record in recording.records)
    repair_calls = max(0, provider_calls - 1)
    complexity: dict[str, object] = {
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
            "initial_authoring_provider_calls": 1 if provider_calls else 0,
            "repair_provider_calls": repair_calls,
            "regeneration_provider_calls": 0,
            "canvas_restarts": 0,
            "repair_mode": "same-canvas-local-pixelprogram",
        },
        "wall_time_ns": result.telemetry["wall_time_ns"],
        "cache_or_profile_reuse": {
            "humanoid_profile_reused": True,
            "pose_profile_reused": True,
            "profile_research_provider_calls": 0,
            "profile_sha256": cast(dict[str, object], humanoid_request["profile_ref"])["sha256"],
            "pose_sha256": cast(dict[str, object], humanoid_request["pose_ref"])["sha256"],
        },
        "failure_category": result.telemetry["failure_category"],
        "human_interventions": result.telemetry["human_interventions"],
        "hidden_scheduler_provider_calls": 0,
        "second_raster_authority": False,
        "skeletal_or_ik_authority_added": False,
        "equipment_specific_raster_authority_added": False,
    }
    complexity["p10_c4_comparison"] = _comparison(complexity)
    _write_json(output_root / "complexity.json", complexity)

    success_reasons: list[str] = []
    if result.loop.status != "finished":
        success_reasons.append(f"loop-status:{result.loop.status}")
    if final_findings:
        success_reasons.append("deterministic-qa-findings-remain")
    if not recording.records:
        success_reasons.append("no-provider-call-recorded")
    if result.telemetry["input_tokens"] is None or result.telemetry["output_tokens"] is None:
        success_reasons.append("exact-provider-token-totals-missing")
    status = "succeeded" if not success_reasons else "failed"

    final_digest = sha256(native.png).hexdigest()
    preview_digest = sha256(preview.png).hexdigest()
    member = BatchReviewMember(
        member_id="g8-h4-static-humanoid",
        asset_class="static-humanoid-character",
        width=width,
        height=height,
        png=native.png,
        source_kind="retained-output",
        source_ref="summary.json",
    )
    package = build_batch_review_package((member,))
    validate_batch_review_package(package)
    if package.manifest["review_scope"] != "retained-output":
        raise SystemExit("G8-H4 review package must remain retained-output scope")
    review_root = output_root / "review-package"
    write_batch_review_package(package, review_root)
    (review_root / "H5_REVIEW.md").write_text(
        "# G8-H5 human perceptual review\n\n"
        "Deterministic QA success is not visual-quality approval. Review the native PNG first, then the 8x preview and bounded-loop snapshots.\n\n"
        "Human-only questions:\n"
        "- Does the face/head read as a deliberate humanoid character at native 1x?\n"
        "- Does the body anatomy look believable for this low-resolution stylization?\n"
        "- Does the grounded three-quarter-right guard pose read clearly?\n"
        "- Is the overall silhouette readable without relying on the enlarged preview?\n"
        "- Is the right-hand short spear clearly attached/readable while the left hand remains free?\n"
        "- Is the overall visual treatment coherent enough to promote static humanoids?\n\n"
        "The files under ../stages are QA-evaluation snapshots, not semantic stage-authority outputs.\n",
        encoding="utf-8",
    )

    summary: dict[str, object] = {
        "phase": "G8",
        "child": "G8-H4",
        "source_issue": 119,
        "source_sha": source_sha.lower(),
        "status": status,
        "failure_reasons": success_reasons,
        "review_scope": "retained-output",
        "owner_verdict": "pending",
        "asset_class": "static-humanoid-character",
        "character_target": "fixture adventurer / grounded three-quarter-right guard / right-hand short spear / left hand clear",
        "canvas": {"width": width, "height": height},
        "request_sha256": humanoid_request["request_sha256"],
        "profile_sha256": cast(dict[str, object], humanoid_request["profile_ref"])["sha256"],
        "pose_sha256": cast(dict[str, object], humanoid_request["pose_ref"])["sha256"],
        "profile_reused": True,
        "pose_reused": True,
        "provider": _provider_environment(provider),
        "final_png": "final.png",
        "final_png_sha256": final_digest,
        "preview_png": f"preview-{PREVIEW_SCALE}x.png",
        "preview_png_sha256": preview_digest,
        "stage_index": "stage-index.json",
        "provider_proposals": "provider-proposals.json",
        "telemetry": "telemetry.json",
        "complexity": "complexity.json",
        "qa_history": "qa-history.json",
        "review_package": "review-package/index.html",
        "review_package_ko": "review-package/index.ko.html",
        "h5_review_guide": "review-package/H5_REVIEW.md",
        "final_aesthetic_acceptance": "human",
        "deterministic_qa_is_visual_quality_success": False,
        "vlm_is_deterministic_correctness": False,
        "new_schema_or_contract_added": False,
        "new_raster_authority_added": False,
        "animation_advanced": False,
        "trace2d_integration_advanced": False,
    }
    _write_json(output_root / "summary.json", summary)
    return summary


def _write_early_failure(output_root: Path, source_sha: str, exc: BaseException) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    failure = {
        "phase": "G8",
        "child": "G8-H4",
        "status": "failed-before-retained-loop-completion",
        "source_sha": source_sha.lower(),
        "failure_type": type(exc).__name__,
        "message": str(exc),
        "contract_first": True,
        "minimal_fix_required_before_new_schema": True,
        "new_schema_or_contract_added": False,
        "new_raster_authority_added": False,
    }
    _write_json(output_root / "failure.json", failure)
    if not (output_root / "summary.json").exists():
        _write_json(
            output_root / "summary.json",
            {
                "phase": "G8",
                "child": "G8-H4",
                "source_issue": 119,
                "source_sha": source_sha.lower(),
                "status": "failed",
                "owner_verdict": "pending",
                "failure_evidence": "failure.json",
                "new_schema_or_contract_added": False,
                "new_raster_authority_added": False,
                "animation_advanced": False,
                "trace2d_integration_advanced": False,
            },
        )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run G8-H4 retained static-humanoid authoring through the existing single-asset authority."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    def provider_factory() -> object:
        return CodexCliProvider(timeout_seconds=PROVIDER_TIMEOUT_SECONDS)

    try:
        summary = run_retained_authoring(
            args.output,
            provider_factory,
            source_sha=args.source_sha,
        )
    except (Exception, SystemExit) as exc:
        _write_early_failure(args.output, args.source_sha, exc)
        print(json.dumps({"status": "failed", "failure": str(exc)}, sort_keys=True))
        return 1

    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0 if summary["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
