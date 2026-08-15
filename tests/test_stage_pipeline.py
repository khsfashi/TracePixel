from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from evidence.p3_s7.fixture import art_intent, stage_plan
from tracepixel.model import (
    STAGE_PIPELINE_EVIDENCE_SCHEMA_V1,
    STAGE_PLAN_SCHEMA_V1,
    STAGE_SEQUENCE_V1,
    StagePipelineValidationError,
    execute_stage_pipeline,
    replay_stage_pipeline_evidence,
    serialize_stage_pipeline_evidence,
    validate_stage_plan,
)

PLAN_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "stage-plan.v1.schema.json"
EVIDENCE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "stage-pipeline-evidence.v1.schema.json"
)


class StagePipelineTests(unittest.TestCase):
    def test_schemas_are_versioned_closed_and_fix_s1_s6_length(self) -> None:
        plan_schema = json.loads(PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
        evidence_schema = json.loads(EVIDENCE_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(STAGE_PLAN_SCHEMA_V1, "tracepixel.stage-plan.v1")
        self.assertEqual(
            STAGE_PIPELINE_EVIDENCE_SCHEMA_V1,
            "tracepixel.stage-pipeline-evidence.v1",
        )
        self.assertEqual(
            STAGE_SEQUENCE_V1,
            (
                "silhouette",
                "major_forms",
                "palette_light_ramp",
                "shading",
                "semantic_details",
                "outline_cleanup",
            ),
        )
        self.assertFalse(plan_schema["additionalProperties"])
        self.assertEqual(plan_schema["properties"]["stages"]["minItems"], 6)
        self.assertEqual(plan_schema["properties"]["stages"]["maxItems"], 6)
        self.assertFalse(evidence_schema["additionalProperties"])
        self.assertEqual(evidence_schema["properties"]["stages"]["minItems"], 6)
        self.assertEqual(evidence_schema["properties"]["stages"]["maxItems"], 6)

    def test_complete_fixture_executes_all_stages_with_preview_and_exact_replay(self) -> None:
        result = execute_stage_pipeline(art_intent(), stage_plan(), preview_scale=2)
        evidence = result.evidence

        self.assertEqual(
            [record["stage"] for record in evidence["stages"]],
            list(STAGE_SEQUENCE_V1),
        )
        self.assertEqual(
            [record["status"] for record in evidence["stages"]],
            ["applied"] * 6,
        )
        self.assertEqual(len(result.previews), 6)
        self.assertEqual(
            [snapshot.stage for snapshot in result.previews],
            list(STAGE_SEQUENCE_V1),
        )
        self.assertEqual(evidence["stages"][0]["input_stage"], "art_intent")
        for previous, current in zip(evidence["stages"], evidence["stages"][1:]):
            self.assertEqual(
                previous["output_rgba_sha256"],
                current["input_rgba_sha256"],
            )
        self.assertEqual(
            evidence["final_rgba_sha256"],
            hashlib.sha256(result.canvas.rgba_bytes()).hexdigest(),
        )
        self.assertEqual(
            evidence["stages"][5]["touched_bounds"],
            {"x": 4, "y": 7, "width": 8, "height": 2},
        )

        replay = replay_stage_pipeline_evidence(evidence)
        self.assertEqual(replay.rgba_bytes(), result.canvas.rgba_bytes())
        self.assertEqual(json.loads(serialize_stage_pipeline_evidence(evidence)), evidence)

    def test_explicit_skip_is_distinct_from_applied_noop_and_preserves_digest(self) -> None:
        plan = stage_plan()
        skipped = plan["stages"][4]
        skipped["document"] = None
        skipped["skip_reason"] = "asset needs no semantic micro-detail"

        result = execute_stage_pipeline(art_intent(), plan)
        record = result.evidence["stages"][4]

        self.assertEqual(record["status"], "skipped")
        self.assertEqual(record["operation_count"], 0)
        self.assertEqual(record["edit_count"], 0)
        self.assertIsNone(record["program"])
        self.assertEqual(record["input_rgba_sha256"], record["output_rgba_sha256"])
        self.assertEqual(
            replay_stage_pipeline_evidence(result.evidence).rgba_bytes(),
            result.canvas.rgba_bytes(),
        )

    def test_applied_empty_stage_is_not_serialized_as_skip(self) -> None:
        plan = stage_plan()
        semantic = plan["stages"][4]
        assert semantic["document"] is not None
        semantic["document"]["details"] = []
        semantic["document"]["program"]["operations"] = []

        result = execute_stage_pipeline(art_intent(), plan)
        record = result.evidence["stages"][4]

        self.assertEqual(record["status"], "applied")
        self.assertIsNone(record["skip_reason"])
        self.assertIsNotNone(record["program"])
        self.assertEqual(record["operation_count"], 0)
        self.assertEqual(record["edit_count"], 0)
        self.assertIsNone(record["touched_bounds"])

    def test_stage_order_is_fixed_and_cannot_be_silently_rearranged(self) -> None:
        plan = stage_plan()
        plan["stages"][0], plan["stages"][1] = plan["stages"][1], plan["stages"][0]

        with self.assertRaises(StagePipelineValidationError) as caught:
            validate_stage_plan(plan, art_intent=art_intent())

        self.assertEqual(caught.exception.code, "invalid_stage_order")
        self.assertEqual(caught.exception.path, "$.stages[0].stage")

    def test_palette_budget_is_enforced_at_s7_cross_stage_boundary(self) -> None:
        intent = art_intent()
        intent["composition"]["palette_budget"] = 6

        with self.assertRaises(StagePipelineValidationError) as caught:
            validate_stage_plan(stage_plan(), art_intent=intent)

        self.assertEqual(caught.exception.code, "palette_budget_exceeded")
        self.assertEqual(caught.exception.path, "$.stages[2].document.palette")

    def test_later_palette_dependent_stage_cannot_apply_after_palette_skip(self) -> None:
        plan = stage_plan()
        palette = plan["stages"][2]
        palette["document"] = None
        palette["skip_reason"] = "palette intentionally omitted for this fixture"

        with self.assertRaises(StagePipelineValidationError) as caught:
            validate_stage_plan(plan, art_intent=art_intent())

        self.assertEqual(caught.exception.code, "missing_stage_context")
        self.assertEqual(caught.exception.path, "$.stages[3].document")

    def test_tampered_transition_digest_is_rejected_by_replay(self) -> None:
        result = execute_stage_pipeline(art_intent(), stage_plan(), preview_scale=2)
        evidence = deepcopy(result.evidence)
        evidence["stages"][3]["output_rgba_sha256"] = "0" * 64

        with self.assertRaises(StagePipelineValidationError) as caught:
            replay_stage_pipeline_evidence(evidence)

        self.assertEqual(caught.exception.code, "output_digest_mismatch")
        self.assertEqual(caught.exception.path, "$.stages[3].output_rgba_sha256")

    def test_tampered_locality_metadata_is_rejected_by_replay(self) -> None:
        result = execute_stage_pipeline(art_intent(), stage_plan())
        evidence = deepcopy(result.evidence)
        evidence["stages"][5]["edit_count"] += 1

        with self.assertRaises(StagePipelineValidationError) as caught:
            replay_stage_pipeline_evidence(evidence)

        self.assertEqual(caught.exception.code, "edit_count_mismatch")
        self.assertEqual(caught.exception.path, "$.stages[5].edit_count")


if __name__ == "__main__":
    unittest.main()
