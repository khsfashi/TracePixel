from __future__ import annotations

import json
from pathlib import Path

from evidence.p7_lane import validate_p7_completion_lane
from tracepixel.qa import QA_POLICY_SCHEMA_V1, analyze_structural, evaluate_qa_policy
from tracepixel.raster import Canvas
from tracepixel.repair import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    REPAIR_EVIDENCE_SCHEMA_V1,
    build_repair_evidence,
    create_repair_plan,
    localize_feedback_intake,
    validate_repair_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "repair-evidence.v1.schema.json"
CORE_LANE_PATH = ROOT / "config" / "tracepixel.core-lane.json"


class _QaEvaluator:
    def evaluate(self, canvas: Canvas) -> dict[str, object]:
        policy = {
            "schema": QA_POLICY_SCHEMA_V1,
            "rules": [{"rule": "structural.no_edge_contact", "severity": "error"}],
        }
        return evaluate_qa_policy(policy, structural=analyze_structural(canvas))


def _plan() -> dict[str, object]:
    intake = {
        "schema": FEEDBACK_INTAKE_SCHEMA_V1,
        "target": {
            "asset_id": "checkpoint-asset-with-a-long-mobile-safe-label",
            "task_id": "P7-F4-checkpoint",
            "canvas": {"width": 4, "height": 4},
            "artifact_sha256": None,
        },
        "items": [
            {
                "id": "edge-repair",
                "authority": "deterministic_qa",
                "source_ref": "checkpoint:qa",
                "summary": "Move visible occupancy away from the left edge.",
                "stage_hint": "silhouette",
                "region_hint": {"x": 0, "y": 1, "width": 2, "height": 1},
                "deterministic_qa": {
                    "rule": "structural.no_edge_contact",
                    "category": "structural",
                    "severity": "error",
                },
                "human": None,
            },
            {
                "id": "owner-defer",
                "authority": "owner_human",
                "source_ref": "checkpoint:owner",
                "summary": "Owner perception remains deferred until the bounded F5 contract.",
                "stage_hint": None,
                "region_hint": None,
                "deterministic_qa": None,
                "human": {
                    "human_rejection": True,
                    "scores": [{"dimension": "style_coherence", "value": 2}],
                },
            },
        ],
    }
    localization = localize_feedback_intake(intake)
    return create_repair_plan(
        localization,
        [
            {
                "feedback_id": "edge-repair",
                "target_stage": "silhouette",
                "program": {
                    "schema": "tracepixel.pixel-program.v1",
                    "canvas": {"width": 4, "height": 4},
                    "operations": [
                        {
                            "op": "set_pixels",
                            "pixels": [
                                [0, 1, 0, 0, 0, 0],
                                [1, 1, 255, 0, 0, 255],
                            ],
                        }
                    ],
                },
                "defer_reason": None,
            },
            {
                "feedback_id": "owner-defer",
                "target_stage": None,
                "program": None,
                "defer_reason": "No explicit owner repair pixels are available yet.",
            },
        ],
    )


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if schema.get("$id") != "urn:tracepixel:schema:repair-evidence:v1":
        raise SystemExit("P7-F4 schema id mismatch")
    if schema.get("additionalProperties") is not False:
        raise SystemExit("P7-F4 root schema must fail closed")

    canvas = Canvas(4, 4)
    canvas.set_pixels(
        [
            (0, 1, (255, 0, 0, 255)),
            (1, 1, (255, 0, 0, 255)),
        ]
    )
    bundle = build_repair_evidence(
        _plan(),
        canvas=canvas,
        qa_evaluator=_QaEvaluator(),
        preview_scale=8,
    )
    manifest = validate_repair_evidence(bundle.manifest)

    if manifest["schema"] != REPAIR_EVIDENCE_SCHEMA_V1:
        raise SystemExit("P7-F4 result schema mismatch")
    execution = manifest["execution"]
    if execution["source_rgba_sha256"] == execution["result_rgba_sha256"]:
        raise SystemExit("P7-F4 checkpoint repair did not change authoritative raster identity")
    if execution["observed_changed_pixel_count"] != 1:
        raise SystemExit("P7-F4 must retain exact F3 changed-pixel evidence")
    if execution["qa"]["findings"]:
        raise SystemExit("P7-F4 must retain the exact cleared F3 deterministic QA evidence")

    if manifest["before_native_png"]["authoritative_rgba_sha256"] != execution["source_rgba_sha256"]:
        raise SystemExit("P7-F4 before native PNG is not bound to the F3 source raster")
    if manifest["before_preview_png"]["authoritative_rgba_sha256"] != execution["source_rgba_sha256"]:
        raise SystemExit("P7-F4 before preview is not bound to the F3 source raster")
    if manifest["after_native_png"]["authoritative_rgba_sha256"] != execution["result_rgba_sha256"]:
        raise SystemExit("P7-F4 after native PNG is not bound to the F3 result raster")
    if manifest["after_preview_png"]["authoritative_rgba_sha256"] != execution["result_rgba_sha256"]:
        raise SystemExit("P7-F4 after preview is not bound to the F3 result raster")

    expected_paths = {
        "manifest.json",
        "before/native.png",
        "before/preview-8x.png",
        "after/native.png",
        "after/preview-8x.png",
        "evidence/qa-findings.json",
        "index.html",
    }
    actual_paths = {item.path for item in bundle.files}
    if actual_paths != expected_paths:
        raise SystemExit(f"P7-F4 materialized path set mismatch: {sorted(actual_paths)!r}")

    gallery = bundle.file_bytes("index.html").decode("utf-8")
    lowered = gallery.lower()
    if "<script" in lowered or "http://" in lowered or "https://" in lowered:
        raise SystemExit("P7-F4 gallery must remain offline and scriptless")
    if "overflow-wrap:anywhere" not in lowered or "grid-template-columns:1fr" not in lowered:
        raise SystemExit("P7-F4 gallery is missing narrow-screen overflow protection")
    if "human feedback remains p7-f5" not in lowered:
        raise SystemExit("P7-F4 gallery lost the human-authority boundary notice")

    root_fields = set(schema["properties"])
    forbidden = {
        "human_feedback",
        "human_approval",
        "human_rejection",
        "perceptual_score",
        "vlm_verdict",
        "all_rules_pass",
        "authoring_complete",
    }
    if root_fields & forbidden:
        raise SystemExit("P7-F4 crossed into F5 human/perceptual completion authority")
    authority = manifest["authority"]
    if authority["human"] != "not-recorded" or authority["perceptual"] != "not-included":
        raise SystemExit("P7-F4 authority declaration crossed the F5/VLM boundary")

    lane = json.loads(CORE_LANE_PATH.read_text(encoding="utf-8"))
    validate_p7_completion_lane(lane, checkpoint_child="P7-F4")

    print("P7-F4 before/after repair evidence checkpoint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
