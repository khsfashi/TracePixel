from __future__ import annotations

import argparse
from copy import deepcopy
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
from tracepixel.model.asset_set_executor import (
    AssetSetMemberExecutionContext,
    SingleAssetExecutionOutput,
    execute_asset_set_schedule,
)
from tracepixel.model.asset_set_schedule import ASSET_SET_REQUEST_SCHEMA_V1, AssetRequestV1
from tracepixel.model.asset_set_schedule_validation import (
    asset_request_sha256,
    asset_set_sha256,
    build_asset_set_schedule,
)
from tracepixel.model.asset_set_validation import validate_asset_set
from tracepixel.preview.batch_review import (
    BatchReviewMember,
    BatchReviewTilePlacement,
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
B3_ROOT = ROOT / "evidence" / "p8_b3"
B4_ROOT = ROOT / "evidence" / "p8_b4"
B3_ASSET_SET = B3_ROOT / "reference-icon-prop-asset-set.v1.json"
B4_ASSET_SET = B4_ROOT / "reference-tile-asset-set.v1.json"
B4_TOPOLOGY = B4_ROOT / "reference-tile-topology.v1.json"

SUMMARY_SCHEMA_V1 = "tracepixel.p8-b5-retained-authoring.v1"
MEMBER_MANIFEST_SCHEMA_V1 = "tracepixel.p8-b5-retained-member.v1"
PRODUCTION_WALL_TIME_MS = 600_000
PROVIDER_TIMEOUT_SECONDS = 120
PREVIEW_SCALE = 8

_LOOP_BUDGET = {
    "schema": AGENT_LOOP_BUDGET_SCHEMA_V1,
    "max_iterations": 4,
    "max_tool_calls": 4,
    "max_operations": 32,
    "max_pixel_edits": 512,
}

ProviderFactory = Callable[[], object]


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise SystemExit(f"{path} must contain a JSON object")
    return cast(dict[str, object], value)


def _request_payloads(asset_set: dict[str, object], root: Path) -> dict[str, object]:
    raw_members = asset_set.get("members")
    if type(raw_members) is not list:
        raise SystemExit("AssetSet members malformed")
    payloads: dict[str, object] = {}
    for raw in cast(list[object], raw_members):
        if type(raw) is not dict:
            raise SystemExit("AssetSet member malformed")
        request_ref = cast(dict[str, object], raw).get("request_ref")
        if type(request_ref) is not str:
            raise SystemExit("AssetSet request_ref malformed")
        payloads[request_ref] = _json(root / request_ref)
    return payloads


def _request_set(asset_set: dict[str, object], payloads: dict[str, object]) -> dict[str, object]:
    raw_members = asset_set.get("members")
    shared_profiles = asset_set.get("shared_profiles")
    if type(raw_members) is not list or type(shared_profiles) is not list:
        raise SystemExit("AssetSet request projection malformed")
    return {
        "schema": ASSET_SET_REQUEST_SCHEMA_V1,
        "asset_set_id": asset_set["asset_set_id"],
        "asset_set_sha256": asset_set_sha256(asset_set),
        "members": [
            {
                "member_id": member["member_id"],
                "request_ref": member["request_ref"],
                "request_sha256": asset_request_sha256(
                    payloads[cast(str, member["request_ref"])],
                    shared_profiles=shared_profiles,
                ),
            }
            for member in cast(list[dict[str, object]], raw_members)
        ],
    }


def _production_asset_set(path: Path) -> dict[str, object]:
    value = deepcopy(_json(path))
    execution = value.get("execution")
    if type(execution) is not dict:
        raise SystemExit("AssetSet execution malformed")
    budget = cast(dict[str, object], execution).get("aggregate_budget")
    if type(budget) is not dict:
        raise SystemExit("AssetSet aggregate budget malformed")
    cast(dict[str, object], budget)["max_wall_time_ms"] = PRODUCTION_WALL_TIME_MS
    return cast(dict[str, object], validate_asset_set(value))


def _canvas_shape(request: AssetRequestV1) -> tuple[int, int, str, int, str | None]:
    art_intent = request["art_intent"]
    canvas = art_intent["canvas"]
    composition = art_intent["composition"]
    symmetry = composition["symmetry"]
    required_symmetry: str | None = None
    if type(symmetry) is dict and symmetry.get("strength") == "required":
        axis = symmetry.get("axis")
        if type(axis) is str:
            required_symmetry = axis
    return (
        canvas["width"],
        canvas["height"],
        art_intent["asset_class"],
        composition["palette_budget"],
        required_symmetry,
    )


class _RequestQa:
    def __init__(self, request: AssetRequestV1) -> None:
        _, _, asset_class, palette_budget, required_symmetry = _canvas_shape(request)
        rules: list[dict[str, str]] = [
            {"rule": "structural.non_empty", "severity": "error"},
            {"rule": "structural.no_translucency", "severity": "error"},
            {"rule": "color.maximum_colors", "severity": "error"},
            {"rule": "color.transparent_rgb_policy", "severity": "error"},
            {"rule": "connectivity.single_component", "severity": "error"},
            {"rule": "connectivity.no_isolated_pixels", "severity": "error"},
        ]
        if asset_class != "terrain-tile":
            rules.append({"rule": "structural.no_edge_contact", "severity": "error"})
        if required_symmetry is not None:
            rules.append({"rule": "shape.required_symmetry", "severity": "error"})
        self._policy = {"schema": QA_POLICY_SCHEMA_V1, "rules": rules}
        self._palette_budget = palette_budget
        self._required_symmetry = required_symmetry

    def evaluate(self, canvas: Canvas):
        return evaluate_qa_policy(
            self._policy,
            structural=analyze_structural(canvas),
            color=analyze_color(
                canvas,
                max_colors=self._palette_budget,
                transparent_rgb_policy="require_zero",
            ),
            connectivity=analyze_connectivity(canvas),
            shape_outline=analyze_shape_outline(
                canvas,
                required_symmetry=self._required_symmetry,
            ),
        )


def _pixel_edit_count(proposal: object) -> int:
    if type(proposal) is not dict:
        return 0
    payload = cast(dict[str, object], proposal).get("payload")
    if type(payload) is not dict:
        return 0
    operations = cast(dict[str, object], payload).get("operations")
    if type(operations) is not list:
        return 0
    count = 0
    for raw in cast(list[object], operations):
        if type(raw) is not dict:
            return 0
        pixels = cast(dict[str, object], raw).get("pixels")
        if type(pixels) is not list:
            return 0
        count += len(cast(list[object], pixels))
    return count


class _BudgetedProvider:
    def __init__(self, provider: object, context: AssetSetMemberExecutionContext) -> None:
        self._provider = provider
        self._context = context
        self._calls = 0
        self._last_usage: AgentProviderUsage | None = None

    def propose(self, request, /):
        if self._calls:
            self._context.record_repair("deterministic_qa_remaining")
        self._context.before_provider_call()
        self._calls += 1
        proposal = self._provider.propose(request)
        usage = self._provider.last_usage()
        if not isinstance(usage, AgentProviderUsage):
            raise RuntimeError("provider did not expose exact token usage")
        if usage.input_tokens is None or usage.output_tokens is None:
            raise RuntimeError("provider token usage was incomplete")
        self._context.after_provider_call(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        edit_count = _pixel_edit_count(proposal)
        if edit_count:
            self._context.before_pixel_edits(edit_count)
        self._last_usage = usage
        return proposal

    def last_usage(self, /) -> AgentProviderUsage | None:
        return self._last_usage


class _RetainedSingleAssetExecutor:
    def __init__(self, output_root: Path, provider_factory: ProviderFactory) -> None:
        self._output_root = output_root
        self._provider_factory = provider_factory

    def execute(
        self,
        request: AssetRequestV1,
        /,
        *,
        member_id: str,
        request_sha256: str,
        context: AssetSetMemberExecutionContext,
    ) -> SingleAssetExecutionOutput:
        width, height, asset_class, _, _ = _canvas_shape(request)
        member_root = self._output_root / "members" / member_id
        member_root.mkdir(parents=True, exist_ok=False)

        provider = self._provider_factory()
        budgeted = _BudgetedProvider(provider, context)
        canvas = Canvas(width, height)
        profiles = ", ".join(
            f"{profile['kind']}:{profile['profile_id']}"
            for profile in request["profile_refs"]
        ) or "none"
        edge_instruction = (
            "Terrain tiles may intentionally touch canvas edges and must honor the requested seam semantics."
            if asset_class == "terrain-tile"
            else "Keep visible content off the outer canvas edge."
        )
        instruction = (
            f"{request['instruction']} "
            f"Use the exact {width}x{height} canvas and shared profile identities {profiles}. "
            "Keep visible pixels fully opaque, transparent pixels RGBA-zero, the visible shape connected, "
            f"and stay within the declared palette budget. {edge_instruction} "
            "Return only bounded pixel edits; deterministic QA will decide whether a repair iteration is needed."
        )
        result = run_bounded_edit_loop_with_telemetry(
            budgeted,
            canvas=canvas,
            art_intent=request["art_intent"],
            instruction=instruction,
            qa_evaluator=_RequestQa(request),
            budget=_LOOP_BUDGET,
        )

        native = export_native_png(canvas)
        preview = export_nearest_preview_png(canvas, scale=PREVIEW_SCALE)
        final_path = member_root / "final.png"
        preview_path = member_root / f"preview-{PREVIEW_SCALE}x.png"
        telemetry_path = member_root / "telemetry.json"
        qa_path = member_root / "qa.json"
        manifest_path = member_root / "manifest.json"
        final_path.write_bytes(native.png)
        preview_path.write_bytes(preview.png)
        telemetry_path.write_text(
            json.dumps(result.telemetry, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        findings = result.loop.observation["qa"]["findings"]
        qa_path.write_text(
            json.dumps({"findings": findings}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        success = result.loop.status == "finished" and not findings
        digest = sha256(native.png).hexdigest()
        manifest: dict[str, object] = {
            "schema": MEMBER_MANIFEST_SCHEMA_V1,
            "member_id": member_id,
            "asset_class": asset_class,
            "request_sha256": request_sha256,
            "status": "succeeded" if success else "failed",
            "loop_status": result.loop.status,
            "width": width,
            "height": height,
            "final_png": str(final_path.relative_to(self._output_root)).replace("\\", "/"),
            "final_png_sha256": digest,
            "preview_png": str(preview_path.relative_to(self._output_root)).replace("\\", "/"),
            "telemetry": str(telemetry_path.relative_to(self._output_root)).replace("\\", "/"),
            "qa": str(qa_path.relative_to(self._output_root)).replace("\\", "/"),
            "remaining_findings": findings,
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if not success:
            return SingleAssetExecutionOutput(
                status="failed",
                failure_category=f"authoring.{result.loop.status}",
                failure_reason="deterministic QA did not close cleanly",
            )
        return SingleAssetExecutionOutput(
            status="succeeded",
            result_ref=str(final_path.relative_to(self._output_root)).replace("\\", "/"),
            result_sha256=digest,
            deterministic_qa_ref=str(qa_path.relative_to(self._output_root)).replace("\\", "/"),
            complexity_ref=str(telemetry_path.relative_to(self._output_root)).replace("\\", "/"),
            provenance_ref=str(manifest_path.relative_to(self._output_root)).replace("\\", "/"),
        )


def _run_cohort(
    *,
    asset_set_path: Path,
    request_root: Path,
    output_root: Path,
    provider_factory: ProviderFactory,
) -> tuple[dict[str, object], dict[str, object]]:
    asset_set = _production_asset_set(asset_set_path)
    payloads = _request_payloads(asset_set, request_root)
    request_set = _request_set(asset_set, payloads)
    schedule = build_asset_set_schedule(request_set, asset_set, payloads)
    executor = _RetainedSingleAssetExecutor(output_root, provider_factory)
    report = execute_asset_set_schedule(schedule, request_set, asset_set, payloads, executor)
    return asset_set, cast(dict[str, object], report)


def _tile_layout() -> tuple[BatchReviewTilePlacement, ...]:
    topology = _json(B4_TOPOLOGY)
    raw_members = topology.get("members")
    if type(raw_members) is not list:
        raise SystemExit("P8-B4 topology members malformed")
    placements: list[BatchReviewTilePlacement] = []
    for raw in cast(list[object], raw_members):
        if type(raw) is not dict:
            raise SystemExit("P8-B4 topology member malformed")
        member = cast(dict[str, object], raw)
        member_id = member.get("member_id")
        x = member.get("x")
        y = member.get("y")
        if type(member_id) is not str or type(x) is not int or type(y) is not int:
            raise SystemExit("P8-B4 topology placement malformed")
        placements.append(BatchReviewTilePlacement(member_id=member_id, x=x, y=y))
    return tuple(placements)


def _review_members(output_root: Path, asset_sets: Sequence[dict[str, object]]) -> tuple[BatchReviewMember, ...]:
    members: list[BatchReviewMember] = []
    for asset_set in asset_sets:
        raw_members = asset_set.get("members")
        if type(raw_members) is not list:
            raise SystemExit("AssetSet members malformed while building review package")
        for raw in cast(list[object], raw_members):
            if type(raw) is not dict:
                raise SystemExit("AssetSet member malformed while building review package")
            member_id = cast(str, cast(dict[str, object], raw)["member_id"])
            manifest_path = output_root / "members" / member_id / "manifest.json"
            manifest = _json(manifest_path)
            if manifest.get("status") != "succeeded":
                raise SystemExit(f"retained authoring member failed deterministic QA: {member_id}")
            final_ref = cast(str, manifest["final_png"])
            final_path = output_root / final_ref
            png = final_path.read_bytes()
            digest = sha256(png).hexdigest()
            if digest != manifest.get("final_png_sha256"):
                raise SystemExit(f"retained PNG digest drifted: {member_id}")
            members.append(
                BatchReviewMember(
                    member_id=member_id,
                    asset_class=cast(str, manifest["asset_class"]),
                    width=cast(int, manifest["width"]),
                    height=cast(int, manifest["height"]),
                    png=png,
                    source_kind="retained-output",
                    source_ref=str(manifest_path.relative_to(output_root)).replace("\\", "/"),
                )
            )
    return tuple(members)


def run_retained_authoring(output_root: Path, provider_factory: ProviderFactory) -> dict[str, object]:
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty output directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    b3_asset_set, b3_report = _run_cohort(
        asset_set_path=B3_ASSET_SET,
        request_root=B3_ROOT,
        output_root=output_root,
        provider_factory=provider_factory,
    )
    b4_asset_set, b4_report = _run_cohort(
        asset_set_path=B4_ASSET_SET,
        request_root=B4_ROOT,
        output_root=output_root,
        provider_factory=provider_factory,
    )
    reports = (b3_report, b4_report)
    failed = [
        cast(str, member_id)
        for report in reports
        for member_id in cast(list[object], report["failed_member_ids"])
    ]
    if failed:
        raise SystemExit(f"retained authoring failed before owner review: {failed}")
    for report in reports:
        if report["declared_max_concurrency"] != 2:
            raise SystemExit("P8-B5 retained authoring must keep reduced parallelism at max_concurrency=2")
        if cast(int, report["observed_peak_live_members"]) > 2:
            raise SystemExit("P8-B5 observed concurrency exceeded the frozen reduced-parallel lane")
        if report["scheduler_provider_calls"] != 0:
            raise SystemExit("P8-B5 scheduler must remain provider-free")

    execution_root = output_root / "execution"
    execution_root.mkdir(exist_ok=False)
    (execution_root / "p8-b3-report.json").write_text(
        json.dumps(b3_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (execution_root / "p8-b4-report.json").write_text(
        json.dumps(b4_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    review_members = _review_members(output_root, (b3_asset_set, b4_asset_set))
    package = build_batch_review_package(review_members, tile_layout=_tile_layout())
    validate_batch_review_package(package)
    if package.manifest["review_scope"] != "retained-output":
        raise SystemExit("real authoring review package must be retained-output scope")
    review_root = output_root / "review-package"
    write_batch_review_package(package, review_root)

    summary: dict[str, object] = {
        "schema": SUMMARY_SCHEMA_V1,
        "review_scope": "retained-output",
        "member_count": len(review_members),
        "cohorts": [b3_asset_set["asset_set_id"], b4_asset_set["asset_set_id"]],
        "declared_max_concurrency": 2,
        "production_wall_time_ms": PRODUCTION_WALL_TIME_MS,
        "aggregate_provider_calls": sum(cast(int, report["aggregate_provider_calls"]) for report in reports),
        "aggregate_pixel_edits": sum(cast(int, report["aggregate_pixel_edits"]) for report in reports),
        "owner_review_required_before_p8_b6": True,
        "owner_verdict": "pending",
        "review_package": "review-package/index.html",
        "review_package_ko": "review-package/index.ko.html",
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the owner-triggered P8-B5 retained-output authoring and mobile review package."
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    def provider_factory() -> object:
        return CodexCliProvider(timeout_seconds=PROVIDER_TIMEOUT_SECONDS)

    summary = run_retained_authoring(args.output, provider_factory)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
