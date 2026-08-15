from __future__ import annotations

import json
from pathlib import Path
import unittest

from tracepixel.agent import (
    AGENT_OBSERVATION_SCHEMA_V1,
    MAX_AGENT_PREVIEW_BYTES_V1,
    MAX_AGENT_RECENT_REVISIONS_V1,
    AgentObservationContractError,
    build_agent_observation,
    validate_agent_observation,
)
from tracepixel.model import ART_INTENT_SCHEMA_V1
from tracepixel.qa import QA_FINDINGS_SCHEMA_V1

ROOT = Path(__file__).resolve().parents[1]
OBSERVATION_SCHEMA_PATH = ROOT / "schemas" / "agent-observation.v1.schema.json"
REQUEST_SCHEMA_PATH = ROOT / "schemas" / "agent-provider-request.v1.schema.json"


def _intent() -> dict[str, object]:
    return {
        "schema": ART_INTENT_SCHEMA_V1,
        "asset_class": "icon",
        "canvas": {"width": 16, "height": 16},
        "composition": {
            "occupied_bounds": {"x": 2, "y": 2, "width": 12, "height": 12},
            "facing": "right",
            "symmetry": None,
            "light_direction": "top_left",
            "palette_budget": 8,
        },
    }


def _findings() -> dict[str, object]:
    return {
        "schema": QA_FINDINGS_SCHEMA_V1,
        "findings": [
            {
                "rule": "connectivity.no_isolated_pixels",
                "category": "connectivity",
                "severity": "warning",
            }
        ],
    }


class AgentObservationContractTests(unittest.TestCase):
    def test_schema_is_closed_versioned_and_request_refs_it(self) -> None:
        schema = json.loads(OBSERVATION_SCHEMA_PATH.read_text(encoding="utf-8"))
        request_schema = json.loads(REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["properties"]["schema"]["const"],
            AGENT_OBSERVATION_SCHEMA_V1,
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["recent"]["maxItems"], MAX_AGENT_RECENT_REVISIONS_V1)
        self.assertEqual(
            request_schema["properties"]["observation"]["$ref"],
            "agent-observation.v1.schema.json",
        )

    def test_builder_emits_only_bounded_summary_and_copies_inputs(self) -> None:
        intent = _intent()
        findings = _findings()
        recent = [
            {
                "revision": 1,
                "stage": "major_forms",
                "proposal_kind": "stage_plan",
                "operation_count": 2,
                "changed_pixels": 24,
            }
        ]

        observation = build_agent_observation(
            art_intent=intent,  # type: ignore[arg-type]
            current_stage="palette_light_ramp",
            revision=2,
            qa_findings=findings,  # type: ignore[arg-type]
            recent=recent,  # type: ignore[arg-type]
        )

        self.assertEqual(
            set(observation),
            {"schema", "intent", "current", "qa", "preview", "recent"},
        )
        self.assertIsNone(observation["preview"])
        self.assertEqual(observation["current"], {"stage": "palette_light_ramp", "revision": 2})
        self.assertIsNot(observation["intent"], intent)
        self.assertIsNot(observation["qa"], findings)
        self.assertIsNot(observation["recent"], recent)

        intent["asset_class"] = "mutated"
        findings["findings"] = []
        recent[0]["changed_pixels"] = 999
        self.assertEqual(observation["intent"]["asset_class"], "icon")
        self.assertEqual(len(observation["qa"]["findings"]), 1)
        self.assertEqual(observation["recent"][0]["changed_pixels"], 24)

    def test_recent_context_is_bounded_ordered_and_before_current_revision(self) -> None:
        observation = build_agent_observation(
            art_intent=_intent(),  # type: ignore[arg-type]
            current_stage="shading",
            revision=10,
            qa_findings={"schema": QA_FINDINGS_SCHEMA_V1, "findings": []},
            recent=[
                {
                    "revision": revision,
                    "stage": "palette_light_ramp",
                    "proposal_kind": "pixel_program",
                    "operation_count": 1,
                    "changed_pixels": 3,
                }
                for revision in range(6, 10)
            ],
        )
        self.assertEqual(len(observation["recent"]), MAX_AGENT_RECENT_REVISIONS_V1)

        observation["recent"].append(
            {
                "revision": 10,
                "stage": "shading",
                "proposal_kind": "pixel_program",
                "operation_count": 0,
                "changed_pixels": 0,
            }
        )
        with self.assertRaises(AgentObservationContractError) as context:
            validate_agent_observation(observation)
        self.assertEqual(context.exception.code, "recent_context_too_large")

    def test_qa_summary_rejects_rule_category_mismatch(self) -> None:
        observation = build_agent_observation(
            art_intent=_intent(),  # type: ignore[arg-type]
            current_stage=None,
            revision=0,
            qa_findings={"schema": QA_FINDINGS_SCHEMA_V1, "findings": []},
        )
        observation["qa"]["findings"] = [
            {
                "rule": "structural.non_empty",
                "category": "color",
                "severity": "error",
            }
        ]  # type: ignore[list-item]

        with self.assertRaises(AgentObservationContractError) as context:
            validate_agent_observation(observation)
        self.assertEqual(context.exception.code, "qa_category_mismatch")

    def test_preview_is_opt_in_hash_checked_and_size_bounded(self) -> None:
        preview = b"\x89PNG\r\n\x1a\ncompact-preview"
        observation = build_agent_observation(
            art_intent=_intent(),  # type: ignore[arg-type]
            current_stage="outline_cleanup",
            revision=3,
            qa_findings={"schema": QA_FINDINGS_SCHEMA_V1, "findings": []},
            preview_png=preview,
            preview_width=32,
            preview_height=32,
        )
        self.assertIsNotNone(observation["preview"])
        validate_agent_observation(observation)

        assert observation["preview"] is not None
        observation["preview"]["sha256"] = "0" * 64
        with self.assertRaises(AgentObservationContractError) as digest_context:
            validate_agent_observation(observation)
        self.assertEqual(digest_context.exception.code, "preview_digest_mismatch")

        with self.assertRaises(AgentObservationContractError) as size_context:
            build_agent_observation(
                art_intent=_intent(),  # type: ignore[arg-type]
                current_stage=None,
                revision=0,
                qa_findings={"schema": QA_FINDINGS_SCHEMA_V1, "findings": []},
                preview_png=b"\x89PNG\r\n\x1a\n" + b"x" * MAX_AGENT_PREVIEW_BYTES_V1,
                preview_width=1,
                preview_height=1,
            )
        self.assertEqual(size_context.exception.code, "preview_too_large")


if __name__ == "__main__":
    unittest.main()
