from __future__ import annotations

from copy import deepcopy
import unittest

from tracepixel.model.research_profile import FORM_RESOLUTION_SCHEMA_V1, MORPHOLOGY_PROFILE_SCHEMA_V1
from tracepixel.model.research_profile_validation import (
    ResearchProfileValidationError,
    morphology_profile_sha256,
    validate_form_resolution,
    validate_morphology_profile,
    validate_morphology_profile_reference,
)


def _profile() -> dict[str, object]:
    return {
        "schema": MORPHOLOGY_PROFILE_SCHEMA_V1,
        "profile_id": "fixture-arthropod-form",
        "subject_label": "Synthetic arthropod-like fixture form",
        "source_evidence": [
            {
                "source_id": "fixture-source-a",
                "kind": "academic",
                "locator": "fixture://research/source-a",
                "title": "Synthetic morphology reference A",
                "retrieved_at_utc": "2026-08-17T06:00:00Z",
            },
            {
                "source_id": "fixture-source-b",
                "kind": "museum",
                "locator": "fixture://research/source-b",
                "title": "Synthetic morphology reference B",
                "retrieved_at_utc": "2026-08-17T06:01:00Z",
            },
        ],
        "observed_facts": [
            {
                "fact_id": "paired-appendages",
                "text": "The synthetic references describe paired articulated appendages attached to the main body mass.",
                "source_ids": ["fixture-source-a", "fixture-source-b"],
            },
            {
                "fact_id": "segment-breaks",
                "text": "The synthetic references distinguish multiple visible segment breaks along each appendage.",
                "source_ids": ["fixture-source-a"],
            },
        ],
        "inferred_constraints": [
            {
                "constraint_id": "retain-paired-silhouette",
                "text": "A recognizable simplified sprite should preserve a paired appendage silhouette before small surface detail.",
                "basis_fact_ids": ["paired-appendages"],
                "confidence": "medium",
            }
        ],
        "artistic_conventions": [
            {
                "convention_id": "low-res-segment-exaggeration",
                "text": "At very low resolution, segment breaks may be exaggerated by one pixel when needed for readability.",
            }
        ],
        "unknowns": [
            {
                "unknown_id": "exact-pixel-ratio",
                "text": "No universal pixel-space segment ratio is asserted by this fixture profile.",
            }
        ],
    }


def _research_required() -> dict[str, object]:
    return {
        "schema": FORM_RESOLUTION_SCHEMA_V1,
        "form_id": "new-arthropod-form",
        "resolution": "research_required",
        "profile_ref": None,
        "research_request": {
            "goal": "Identify silhouette-critical morphology before pixel authoring.",
            "allowed_source_kinds": ["academic", "museum", "encyclopedic"],
            "budget": {
                "max_sources": 6,
                "max_search_calls": 4,
                "max_fetch_calls": 8,
                "max_wall_time_ms": 300000,
            },
        },
    }


class ResearchProfileTests(unittest.TestCase):
    def test_research_required_is_explicit_and_bounded(self) -> None:
        resolution = _research_required()
        self.assertIs(resolution, validate_form_resolution(resolution))

    def test_resolution_states_are_mutually_exclusive(self) -> None:
        profile = _profile()
        ref = {
            "profile_id": profile["profile_id"],
            "profile_schema": MORPHOLOGY_PROFILE_SCHEMA_V1,
            "sha256": morphology_profile_sha256(profile),
        }
        known = {
            "schema": FORM_RESOLUTION_SCHEMA_V1,
            "form_id": "fixture-arthropod-form",
            "resolution": "known_profile",
            "profile_ref": ref,
            "research_request": None,
        }
        self.assertIs(known, validate_form_resolution(known))

        invalid = deepcopy(known)
        invalid["research_request"] = _research_required()["research_request"]
        with self.assertRaisesRegex(ResearchProfileValidationError, "invalid_resolution_state"):
            validate_form_resolution(invalid)

    def test_research_budget_rejects_bool_zero_and_unbounded_values(self) -> None:
        cases = (
            ("max_sources", True),
            ("max_search_calls", 0),
            ("max_fetch_calls", 17),
            ("max_wall_time_ms", 600001),
        )
        for field, value in cases:
            resolution = _research_required()
            request = resolution["research_request"]
            assert type(request) is dict
            budget = request["budget"]
            assert type(budget) is dict
            budget[field] = value
            with self.assertRaises(ResearchProfileValidationError):
                validate_form_resolution(resolution)

    def test_source_evidence_is_identity_only_and_cannot_embed_source_bodies(self) -> None:
        profile = _profile()
        sources = profile["source_evidence"]
        assert type(sources) is list and type(sources[0]) is dict
        sources[0]["image_bytes"] = "copied-source-payload"
        with self.assertRaisesRegex(ResearchProfileValidationError, "invalid_fields"):
            validate_morphology_profile(profile)

    def test_observed_facts_must_reference_retained_sources(self) -> None:
        profile = _profile()
        facts = profile["observed_facts"]
        assert type(facts) is list and type(facts[0]) is dict
        facts[0]["source_ids"] = ["missing-source"]
        with self.assertRaisesRegex(ResearchProfileValidationError, "unknown_source_reference"):
            validate_morphology_profile(profile)

    def test_inferences_must_bind_to_observed_facts(self) -> None:
        profile = _profile()
        constraints = profile["inferred_constraints"]
        assert type(constraints) is list and type(constraints[0]) is dict
        constraints[0]["basis_fact_ids"] = ["invented-fact"]
        with self.assertRaisesRegex(ResearchProfileValidationError, "unknown_fact_reference"):
            validate_morphology_profile(profile)

    def test_profile_digest_is_canonical_and_reference_is_exact(self) -> None:
        profile = _profile()
        digest = morphology_profile_sha256(profile)
        reordered = {
            key: profile[key]
            for key in reversed(list(profile))
        }
        self.assertEqual(digest, morphology_profile_sha256(reordered))

        ref = {
            "profile_id": profile["profile_id"],
            "profile_schema": MORPHOLOGY_PROFILE_SCHEMA_V1,
            "sha256": digest,
        }
        self.assertIs(ref, validate_morphology_profile_reference(ref, profile))
        ref["sha256"] = "0" * 64
        with self.assertRaisesRegex(ResearchProfileValidationError, "profile_digest_mismatch"):
            validate_morphology_profile_reference(ref, profile)

    def test_facts_inferences_conventions_and_unknowns_stay_separate(self) -> None:
        profile = _profile()
        self.assertIs(profile, validate_morphology_profile(profile))
        fact = profile["observed_facts"][0]
        convention = profile["artistic_conventions"][0]
        self.assertIn("source_ids", fact)
        self.assertNotIn("source_ids", convention)


if __name__ == "__main__":
    unittest.main()
