from __future__ import annotations

import json
from pathlib import Path
import unittest

from tracepixel.agent import (
    AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
    AGENT_PROVIDER_REQUEST_SCHEMA_V1,
    AgentProvider,
    AgentProviderContractError,
    AgentProviderProposalV1,
    AgentProviderRequestV1,
    validate_agent_provider_proposal,
    validate_agent_provider_request,
)
from tracepixel.model import (
    ART_INTENT_SCHEMA_V1,
    PIXEL_PROGRAM_SCHEMA_V1,
    SET_PIXELS_OPERATION_V1,
    STAGE_PLAN_SCHEMA_V1,
    STAGE_SEQUENCE_V1,
)


ROOT = Path(__file__).resolve().parents[1]
REQUEST_SCHEMA_PATH = ROOT / "schemas" / "agent-provider-request.v1.schema.json"
PROPOSAL_SCHEMA_PATH = ROOT / "schemas" / "agent-provider-proposal.v1.schema.json"


def _request() -> AgentProviderRequestV1:
    return {
        "schema": AGENT_PROVIDER_REQUEST_SCHEMA_V1,
        "instruction": "Add one bounded exact-pixel edit.",
        "observation": {
            "stage": "semantic_details",
            "revision": 2,
            "flags": ["provider-neutral", True, None],
        },
    }


def _pixel_program_proposal() -> AgentProviderProposalV1:
    return {
        "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
        "kind": "pixel_program",
        "payload": {
            "schema": PIXEL_PROGRAM_SCHEMA_V1,
            "canvas": {"width": 2, "height": 2},
            "operations": [
                {
                    "op": SET_PIXELS_OPERATION_V1,
                    "pixels": [[1, 1, 10, 20, 30, 255]],
                }
            ],
        },
    }


def _art_intent() -> dict[str, object]:
    return {
        "schema": ART_INTENT_SCHEMA_V1,
        "asset_class": "icon",
        "canvas": {"width": 2, "height": 2},
        "composition": {
            "occupied_bounds": None,
            "facing": None,
            "symmetry": None,
            "light_direction": None,
            "palette_budget": None,
        },
    }


def _skipped_stage_plan_proposal() -> AgentProviderProposalV1:
    return {
        "schema": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
        "kind": "stage_plan",
        "payload": {
            "schema": STAGE_PLAN_SCHEMA_V1,
            "stages": [
                {
                    "stage": stage,
                    "document": None,
                    "skip_reason": "No authored edit is required for this stage.",
                }
                for stage in STAGE_SEQUENCE_V1
            ],
        },
    }


class _FakeProvider:
    def propose(self, request: AgentProviderRequestV1, /) -> AgentProviderProposalV1:
        validate_agent_provider_request(request)
        return _pixel_program_proposal()


class AgentProviderContractTests(unittest.TestCase):
    def test_schema_identities_are_versioned_and_envelopes_are_closed(self) -> None:
        request_schema = json.loads(REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        proposal_schema = json.loads(PROPOSAL_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            request_schema["properties"]["schema"]["const"],
            AGENT_PROVIDER_REQUEST_SCHEMA_V1,
        )
        self.assertEqual(
            proposal_schema["properties"]["schema"]["const"],
            AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
        )
        self.assertFalse(request_schema["additionalProperties"])
        self.assertFalse(proposal_schema["additionalProperties"])
        self.assertEqual(
            proposal_schema["properties"]["kind"]["enum"],
            ["pixel_program", "stage_plan"],
        )

    def test_request_is_plain_json_data_and_validation_does_not_copy_it(self) -> None:
        request = _request()

        validated = validate_agent_provider_request(request)

        self.assertIs(validated, request)
        self.assertEqual(json.loads(json.dumps(request)), request)

    def test_request_rejects_provider_sdk_objects_and_non_finite_numbers(self) -> None:
        request = _request()
        request["observation"]["sdk"] = object()  # type: ignore[assignment]

        with self.assertRaises(AgentProviderContractError) as sdk_context:
            validate_agent_provider_request(request)
        self.assertEqual(sdk_context.exception.code, "invalid_json_value")
        self.assertEqual(sdk_context.exception.path, "$.observation['sdk']")

        request = _request()
        request["observation"]["score"] = float("nan")
        with self.assertRaises(AgentProviderContractError) as number_context:
            validate_agent_provider_request(request)
        self.assertEqual(number_context.exception.code, "invalid_json_value")
        self.assertEqual(number_context.exception.path, "$.observation['score']")

    def test_fake_provider_satisfies_runtime_protocol_and_returns_valid_candidate(self) -> None:
        provider = _FakeProvider()
        self.assertIsInstance(provider, AgentProvider)

        proposal = provider.propose(_request())
        validated = validate_agent_provider_proposal(proposal)

        self.assertIs(validated, proposal)
        self.assertEqual(validated["kind"], "pixel_program")

    def test_pixel_program_candidate_delegates_to_existing_validator(self) -> None:
        proposal = _pixel_program_proposal()
        proposal["payload"]["operations"][0]["pixels"][0][5] = 256  # type: ignore[index]

        with self.assertRaises(AgentProviderContractError) as context:
            validate_agent_provider_proposal(proposal)

        self.assertEqual(context.exception.code, "invalid_proposal_payload")
        self.assertTrue(
            context.exception.path.startswith("$.payload.operations[0].pixels[0]")
        )
        self.assertIn("invalid_color", context.exception.message)

    def test_stage_plan_candidate_requires_external_art_intent_context(self) -> None:
        proposal = _skipped_stage_plan_proposal()

        with self.assertRaises(AgentProviderContractError) as missing_context:
            validate_agent_provider_proposal(proposal)
        self.assertEqual(missing_context.exception.code, "missing_validation_context")
        self.assertEqual(missing_context.exception.path, "$context.art_intent")

        validated = validate_agent_provider_proposal(
            proposal,
            art_intent=_art_intent(),
        )
        self.assertIs(validated, proposal)
        self.assertEqual(validated["kind"], "stage_plan")


if __name__ == "__main__":
    unittest.main()
