from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import struct
from typing import Callable, Sequence, cast
import zlib

from tracepixel.agent import CodexCliProvider
from tracepixel.model.asset_set_executor import execute_asset_set_schedule
from tracepixel.model.asset_set_schedule_validation import build_asset_set_schedule
from tracepixel.model.asset_set_validation import validate_asset_set
from tracepixel.preview.batch_review import (
    build_batch_review_package,
    validate_batch_review_package,
    write_batch_review_package,
)

from evidence.p8_b5.retained_authoring import (
    B3_ASSET_SET,
    B3_ROOT,
    B4_ASSET_SET,
    B4_ROOT,
    MEMBER_MANIFEST_SCHEMA_V1,
    PROVIDER_TIMEOUT_SECONDS,
    SUMMARY_SCHEMA_V1,
    _RetainedSingleAssetExecutor,
    _json,
    _production_asset_set,
    _request_payloads,
    _request_set,
    _review_members,
    _tile_layout,
)

ROOT = Path(__file__).resolve().parents[2]
OWNER_REVIEW = ROOT / "evidence" / "p8_b5" / "owner-review-32022902199.json"
OWNER_REVIEW_SCHEMA_V1 = "tracepixel.p8-b5-owner-review.v1"
REPAIR_SUMMARY_SCHEMA_V1 = "tracepixel.p8-b5-retained-repair.v1"
REPAIR_RECORD_SCHEMA_V1 = "tracepixel.p8-b5-retained-repair-record.v1"
REPAIR_MEMBER_ID = "grass-center-b"
REPAIR_ASSET_SET_ID = "p8-b5-grass-center-b-repair"
EXPECTED_SOURCE_RUN_ID = 32022902199
EXPECTED_SOURCE_ARTIFACT = "p8-b5-retained-authoring-32022902199"

_OWNER_REPAIR_SUFFIX = (
    " Owner perceptual review rejected only this prior member because a visible hole or missing-pixel "
    "defect remained. Re-author this member only. The complete 16x16 grass center tile must contain "
    "fully opaque grass in every pixel; leave no transparent or empty pixel anywhere. Preserve the "
    "requested top-down grass-center semantics, shared style/palette identities, and no dirt transition."
)

ProviderFactory = Callable[[], object]


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _member_records(gate: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    accepted = gate.get("accepted_members")
    rejected = gate.get("rejected_members")
    if type(accepted) is not list or type(rejected) is not list:
        raise SystemExit("P8-B5 owner review member records are malformed")
    if not all(type(item) is dict for item in accepted + rejected):
        raise SystemExit("P8-B5 owner review member records must be JSON objects")
    return (
        cast(list[dict[str, object]], accepted),
        cast(list[dict[str, object]], rejected),
    )


def _current_request_shas() -> dict[str, str]:
    result: dict[str, str] = {}
    for asset_set_path, request_root in ((B3_ASSET_SET, B3_ROOT), (B4_ASSET_SET, B4_ROOT)):
        asset_set = _production_asset_set(asset_set_path)
        payloads = _request_payloads(asset_set, request_root)
        request_set = _request_set(asset_set, payloads)
        for member in request_set["members"]:
            member_id = cast(str, member["member_id"])
            result[member_id] = cast(str, member["request_sha256"])
    return result


def _validate_gate(gate: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, object]]:
    if gate.get("schema") != OWNER_REVIEW_SCHEMA_V1:
        raise SystemExit("unsupported P8-B5 owner review schema")
    if gate.get("source_run_id") != EXPECTED_SOURCE_RUN_ID:
        raise SystemExit("owner review must remain pinned to workflow run 32022902199")
    if gate.get("source_artifact_name") != EXPECTED_SOURCE_ARTIFACT:
        raise SystemExit("owner review source artifact drifted")
    if gate.get("review_scope") != "retained-output":
        raise SystemExit("owner review must be retained-output scope")
    if gate.get("verdict") != "partial-accept-repair-required":
        raise SystemExit("localized repair requires the recorded partial owner verdict")

    accepted, rejected = _member_records(gate)
    if len(accepted) != 7 or len(rejected) != 1:
        raise SystemExit("localized repair requires exactly seven accepted members and one rejected member")
    rejected_record = rejected[0]
    if rejected_record.get("member_id") != REPAIR_MEMBER_ID:
        raise SystemExit("only grass-center-b is authorized for the P8-B5 localized repair")
    if rejected_record.get("action") != "re-author-member-only":
        raise SystemExit("owner review does not authorize member-local re-authoring")
    if rejected_record.get("feedback") != "visible hole / missing-pixel defect":
        raise SystemExit("owner feedback drifted from the recorded perceptual defect")

    current_shas = _current_request_shas()
    seen: set[str] = set()
    for record in accepted + rejected:
        member_id = record.get("member_id")
        request_sha = record.get("request_sha256")
        final_sha = record.get("final_png_sha256")
        if type(member_id) is not str or member_id in seen:
            raise SystemExit("owner review member identities must be unique strings")
        if type(request_sha) is not str or len(request_sha) != 64:
            raise SystemExit(f"owner review request digest malformed: {member_id}")
        if type(final_sha) is not str or len(final_sha) != 64:
            raise SystemExit(f"owner review PNG digest malformed: {member_id}")
        if current_shas.get(member_id) != request_sha:
            raise SystemExit(f"current request identity drifted since owner review: {member_id}")
        seen.add(member_id)
    if seen != set(current_shas):
        raise SystemExit("owner review membership no longer matches the representative P8-B5 cohorts")
    return accepted, rejected_record


def _validate_source_member(source_root: Path, record: dict[str, object]) -> dict[str, object]:
    member_id = cast(str, record["member_id"])
    manifest_path = source_root / "members" / member_id / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"reviewed source member manifest missing: {member_id}")
    manifest = _json(manifest_path)
    if manifest.get("schema") != MEMBER_MANIFEST_SCHEMA_V1 or manifest.get("status") != "succeeded":
        raise SystemExit(f"reviewed source member is not a retained successful output: {member_id}")
    if manifest.get("request_sha256") != record["request_sha256"]:
        raise SystemExit(f"reviewed source request digest drifted: {member_id}")
    if manifest.get("final_png_sha256") != record["final_png_sha256"]:
        raise SystemExit(f"reviewed source manifest PNG digest drifted: {member_id}")
    final_ref = manifest.get("final_png")
    if final_ref != f"members/{member_id}/final.png":
        raise SystemExit(f"reviewed source final PNG path is unexpected: {member_id}")
    final_path = source_root / cast(str, final_ref)
    if not final_path.is_file() or _sha256_file(final_path) != record["final_png_sha256"]:
        raise SystemExit(f"reviewed source PNG bytes drifted: {member_id}")
    return manifest


def _validate_source(
    source_root: Path,
    accepted: list[dict[str, object]],
    rejected: dict[str, object],
) -> dict[str, object]:
    summary_path = source_root / "summary.json"
    if not summary_path.is_file():
        raise SystemExit("reviewed P8-B5 source summary is missing")
    summary = _json(summary_path)
    if summary.get("schema") != SUMMARY_SCHEMA_V1:
        raise SystemExit("reviewed P8-B5 source summary schema drifted")
    if summary.get("review_scope") != "retained-output" or summary.get("member_count") != 8:
        raise SystemExit("reviewed P8-B5 source is not the expected eight-member retained-output artifact")
    if summary.get("owner_verdict") != "pending":
        raise SystemExit("source automation must remain non-authoritative for owner perception")
    for record in accepted + [rejected]:
        _validate_source_member(source_root, record)
    return summary


def _copy_preserved_members(
    source_root: Path,
    output_root: Path,
    accepted: list[dict[str, object]],
) -> None:
    members_root = output_root / "members"
    members_root.mkdir(parents=True, exist_ok=False)
    for record in accepted:
        member_id = cast(str, record["member_id"])
        shutil.copytree(source_root / "members" / member_id, members_root / member_id)
        _validate_source_member(output_root, record)


def _repair_asset_set() -> dict[str, object]:
    asset_set = deepcopy(_production_asset_set(B4_ASSET_SET))
    members = cast(list[dict[str, object]], asset_set["members"])
    asset_set["asset_set_id"] = REPAIR_ASSET_SET_ID
    asset_set["members"] = [member for member in members if member["member_id"] == REPAIR_MEMBER_ID]
    execution = cast(dict[str, object], asset_set["execution"])
    execution["max_concurrency"] = 1
    budget = cast(dict[str, object], execution["aggregate_budget"])
    budget["max_provider_calls"] = 4
    budget["max_pixel_edits"] = 512
    return cast(dict[str, object], validate_asset_set(asset_set))


def _repair_payloads(asset_set: dict[str, object]) -> tuple[dict[str, object], str, str]:
    payloads = _request_payloads(asset_set, B4_ROOT)
    members = cast(list[dict[str, object]], asset_set["members"])
    if len(members) != 1:
        raise SystemExit("localized repair asset set must contain exactly one member")
    request_ref = cast(str, members[0]["request_ref"])
    original = cast(dict[str, object], payloads[request_ref])
    original_instruction = original.get("instruction")
    if type(original_instruction) is not str:
        raise SystemExit("localized repair source instruction malformed")
    repaired = deepcopy(original)
    repaired["instruction"] = original_instruction + _OWNER_REPAIR_SUFFIX
    payloads[request_ref] = repaired
    original_request_set = _request_set(asset_set, {request_ref: original})
    repair_request_set = _request_set(asset_set, payloads)
    return (
        payloads,
        cast(str, original_request_set["members"][0]["request_sha256"]),
        cast(str, repair_request_set["members"][0]["request_sha256"]),
    )


def _run_repair_member(
    output_root: Path,
    provider_factory: ProviderFactory,
) -> tuple[dict[str, object], str, str]:
    asset_set = _repair_asset_set()
    payloads, original_request_sha, repair_request_sha = _repair_payloads(asset_set)
    request_set = _request_set(asset_set, payloads)
    schedule = build_asset_set_schedule(request_set, asset_set, payloads)
    executor = _RetainedSingleAssetExecutor(output_root, provider_factory)
    report = cast(
        dict[str, object],
        execute_asset_set_schedule(schedule, request_set, asset_set, payloads, executor),
    )
    if report["declared_max_concurrency"] != 1 or cast(int, report["observed_peak_live_members"]) > 1:
        raise SystemExit("localized repair must execute exactly one member with max_concurrency=1")
    if report["scheduler_provider_calls"] != 0:
        raise SystemExit("localized repair scheduler must remain provider-free")
    if report["failed_member_ids"]:
        raise SystemExit(f"localized retained repair failed: {report['failed_member_ids']}")
    return report, original_request_sha, repair_request_sha


def _decode_tracepixel_native_rgba(png: bytes, *, expected_width: int, expected_height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    if not png.startswith(signature):
        raise SystemExit("localized repair output is not a PNG")
    offset = len(signature)
    width: int | None = None
    height: int | None = None
    idat = bytearray()
    saw_iend = False
    while offset + 12 <= len(png):
        length = struct.unpack_from(">I", png, offset)[0]
        chunk_type = png[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(png):
            raise SystemExit("localized repair PNG chunk is truncated")
        data = png[data_start:data_end]
        if chunk_type == b"IHDR":
            if len(data) != 13:
                raise SystemExit("localized repair PNG IHDR is malformed")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            if (bit_depth, color_type, compression, filter_method, interlace) != (8, 6, 0, 0, 0):
                raise SystemExit("localized repair PNG must remain non-interlaced RGBA8")
        elif chunk_type == b"IDAT":
            idat.extend(data)
        elif chunk_type == b"IEND":
            saw_iend = True
            break
        offset = crc_end
    if not saw_iend or width != expected_width or height != expected_height:
        raise SystemExit("localized repair PNG dimensions or termination drifted")
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise SystemExit("localized repair PNG IDAT could not be decoded") from exc
    stride = expected_width * 4
    expected_length = expected_height * (stride + 1)
    if len(raw) != expected_length:
        raise SystemExit("localized repair PNG decoded byte length drifted")
    rgba = bytearray(expected_width * expected_height * 4)
    target = 0
    source = 0
    for _ in range(expected_height):
        if raw[source] != 0:
            raise SystemExit("localized repair PNG must use TracePixel filter-none rows")
        source += 1
        rgba[target : target + stride] = raw[source : source + stride]
        source += stride
        target += stride
    return bytes(rgba)


def _assert_full_grass_coverage(final_path: Path) -> None:
    rgba = _decode_tracepixel_native_rgba(final_path.read_bytes(), expected_width=16, expected_height=16)
    transparent: list[tuple[int, int]] = []
    for index in range(3, len(rgba), 4):
        if rgba[index] != 255:
            pixel = index // 4
            transparent.append((pixel % 16, pixel // 16))
    if transparent:
        first = transparent[0]
        raise SystemExit(
            "owner-repair completion constraint failed: "
            f"{len(transparent)} non-opaque pixels remain; first at {first}"
        )


def run_retained_repair(
    source_root: Path,
    output_root: Path,
    provider_factory: ProviderFactory,
    *,
    review_gate: dict[str, object] | None = None,
) -> dict[str, object]:
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty output directory: {output_root}")

    gate = deepcopy(review_gate) if review_gate is not None else _json(OWNER_REVIEW)
    accepted, rejected = _validate_gate(cast(dict[str, object], gate))
    source_summary = _validate_source(source_root, accepted, rejected)

    output_root.mkdir(parents=True, exist_ok=True)
    _copy_preserved_members(source_root, output_root, accepted)
    shutil.copy2(source_root / "summary.json", output_root / "source-summary.json")
    if (source_root / "execution").is_dir():
        shutil.copytree(source_root / "execution", output_root / "source-execution")

    report, original_request_sha, repair_request_sha = _run_repair_member(output_root, provider_factory)
    if original_request_sha != rejected["request_sha256"]:
        raise SystemExit("repair source request no longer matches the owner-reviewed rejected member")
    if repair_request_sha == original_request_sha:
        raise SystemExit("owner feedback must be digest-bound into the localized repair request")

    repaired_manifest = _json(output_root / "members" / REPAIR_MEMBER_ID / "manifest.json")
    repaired_ref = cast(str, repaired_manifest["final_png"])
    repaired_path = output_root / repaired_ref
    _assert_full_grass_coverage(repaired_path)
    replacement_sha = _sha256_file(repaired_path)
    if replacement_sha != repaired_manifest.get("final_png_sha256"):
        raise SystemExit("localized repair PNG digest does not match its retained manifest")
    if replacement_sha == rejected["final_png_sha256"]:
        raise SystemExit("localized repair did not replace the owner-rejected PNG")

    for record in accepted:
        _validate_source_member(output_root, record)

    execution_root = output_root / "execution"
    execution_root.mkdir(exist_ok=False)
    (execution_root / "grass-center-b-repair-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    b3_asset_set = _production_asset_set(B3_ASSET_SET)
    b4_asset_set = _production_asset_set(B4_ASSET_SET)
    review_members = _review_members(output_root, (b3_asset_set, b4_asset_set))
    package = build_batch_review_package(review_members, tile_layout=_tile_layout())
    validate_batch_review_package(package)
    if package.manifest["review_scope"] != "retained-output":
        raise SystemExit("localized repair review package must remain retained-output scope")
    review_root = output_root / "review-package"
    write_batch_review_package(package, review_root)

    repair_record: dict[str, object] = {
        "schema": REPAIR_RECORD_SCHEMA_V1,
        "source_run_id": gate["source_run_id"],
        "source_artifact_name": gate["source_artifact_name"],
        "source_artifact_sha256": gate["source_artifact_sha256"],
        "source_owner_verdict": gate["verdict"],
        "preserved_members": [
            {
                "member_id": record["member_id"],
                "request_sha256": record["request_sha256"],
                "final_png_sha256": record["final_png_sha256"],
            }
            for record in accepted
        ],
        "repair_member_id": REPAIR_MEMBER_ID,
        "owner_feedback": rejected["feedback"],
        "prior_request_sha256": original_request_sha,
        "repair_request_sha256": repair_request_sha,
        "prior_png_sha256": rejected["final_png_sha256"],
        "replacement_png_sha256": replacement_sha,
        "completion_constraint": "all 16x16 output pixels have alpha=255",
        "completion_constraint_satisfied": True,
        "owner_re_review_required": True,
    }
    (output_root / "repair-record.json").write_text(
        json.dumps(repair_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    source_provider_calls = cast(int, source_summary["aggregate_provider_calls"])
    source_pixel_edits = cast(int, source_summary["aggregate_pixel_edits"])
    repair_provider_calls = cast(int, report["aggregate_provider_calls"])
    repair_pixel_edits = cast(int, report["aggregate_pixel_edits"])
    summary: dict[str, object] = {
        "schema": REPAIR_SUMMARY_SCHEMA_V1,
        "review_scope": "retained-output",
        "member_count": len(review_members),
        "source_run_id": gate["source_run_id"],
        "source_artifact_name": gate["source_artifact_name"],
        "source_artifact_sha256": gate["source_artifact_sha256"],
        "preserved_member_count": len(accepted),
        "repair_member_id": REPAIR_MEMBER_ID,
        "repair_declared_max_concurrency": report["declared_max_concurrency"],
        "repair_provider_calls": repair_provider_calls,
        "repair_pixel_edits": repair_pixel_edits,
        "source_aggregate_provider_calls": source_provider_calls,
        "source_aggregate_pixel_edits": source_pixel_edits,
        "effective_aggregate_provider_calls": source_provider_calls + repair_provider_calls,
        "effective_aggregate_pixel_edits": source_pixel_edits + repair_pixel_edits,
        "repair_request_sha256": repair_request_sha,
        "replacement_png_sha256": replacement_sha,
        "replacement_changed": True,
        "repair_constraint_satisfied": True,
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
        description="Re-author only the owner-rejected P8-B5 member while preserving accepted retained outputs."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    def provider_factory() -> object:
        return CodexCliProvider(timeout_seconds=PROVIDER_TIMEOUT_SECONDS)

    summary = run_retained_repair(args.source, args.output, provider_factory)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
