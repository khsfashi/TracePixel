from __future__ import annotations

from copy import deepcopy
import unittest

from tracepixel.model.research_profile import MORPHOLOGY_PROFILE_SCHEMA_V1
from tracepixel.model.research_profile_validation import (
    ResearchProfileValidationError,
    morphology_profile_sha256,
    validate_morphology_profile,
    validate_morphology_profile_reference,
    validate_simple_creature_morphology_profile,
)


def _profile() -> dict[str, object]:
    return {
        "schema": MORPHOLOGY_PROFILE_SCHEMA_V1,
        "profile_id": "fixture-simple-creature-v1",
        "subject_label": "Synthetic quadruped-like simple creature",
        "source_evidence": [
            {
                "source_id": "fixture-source-a",
                "kind": "academic",
                "locator": "fixture://p10-c1/source-a",
                "title": "Synthetic morphology source A",
                "retrieved_at_utc": "2026-08-18T01:30:00Z",
            }
        ],
        "observed_facts": [
            {
                "fact_id": "coarse-structure",
                "text": "The synthetic fixture declares a head, trunk, paired supports, and an articulated head-to-trunk relation.",
                "source_ids": ["fixture-source-a"],
            },
            {
                "fact_id": "low-resolution-readability",
                "text": "The synthetic fixture permits bounded low-resolution enlargement of silhouette-critical features.",
                "source_ids": ["fixture-source-a"],
            },
        ],
        "inferred_constraints": [
            {
                "constraint_id": "preserve-coarse-identity",
                "text": "Keep the head/trunk/support grouping readable before surface detail.",
                "basis_fact_ids": ["coarse-structure"],
                "confidence": "high",
            }
        ],
        "artistic_conventions": [
            {
                "convention_id": "pixel-simplification",
                "text": "Very small sprites may exaggerate silhouette-critical features within retained tolerance.",
            }
        ],
        "unknowns": [
            {
                "unknown_id": "exact-neck-axis",
                "text": "The fixture does not assert one universal neck articulation axis.",
            }
        ],
        "creature_structure": {
            "subject": {
                "family_id": "fixture-quadruped-family",
                "species_id": "fixture-species",
                "form_id": "fixture-form-a",
            },
            "landmarks": [
                {
                    "landmark_id": "trunk",
                    "label": "Trunk center",
                    "parent_landmark_id": None,
                    "mirror_landmark_id": None,
                },
                {
                    "landmark_id": "head",
                    "label": "Head center",
                    "parent_landmark_id": "trunk",
                    "mirror_landmark_id": None,
                },
                {
                    "landmark_id": "support-left",
                    "label": "Left support contact",
                    "parent_landmark_id": "trunk",
                    "mirror_landmark_id": "support-right",
                },
                {
                    "landmark_id": "support-right",
                    "label": "Right support contact",
                    "parent_landmark_id": "trunk",
                    "mirror_landmark_id": "support-left",
                },
            ],
            "category_declarations": [
                {
                    "category": "relative-proportion",
                    "status": "constrained",
                    "rationale": "Head-to-trunk scale is part of the coarse form identity.",
                    "unknown_id": None,
                },
                {
                    "category": "symmetry-orientation",
                    "status": "constrained",
                    "rationale": "Paired supports are expected to remain approximately bilateral.",
                    "unknown_id": None,
                },
                {
                    "category": "articulation",
                    "status": "constrained",
                    "rationale": "Head-to-trunk articulation is structurally relevant.",
                    "unknown_id": None,
                },
                {
                    "category": "silhouette-critical",
                    "status": "constrained",
                    "rationale": "The head and paired supports must remain declared silhouette features.",
                    "unknown_id": None,
                },
                {
                    "category": "support-contact",
                    "status": "constrained",
                    "rationale": "The paired support landmarks define expected ground contact.",
                    "unknown_id": None,
                },
                {
                    "category": "resolution-stylization",
                    "status": "constrained",
                    "rationale": "Low-resolution authoring requires an explicit pixel tolerance.",
                    "unknown_id": None,
                },
            ],
            "constraints": [
                {
                    "constraint_id": "head-trunk-ratio",
                    "category": "relative-proportion",
                    "mode": "required-range",
                    "landmark_ids": ["head", "trunk"],
                    "value_range": {"minimum": 0.35, "maximum": 0.65, "unit": "ratio"},
                    "text": "Retain a bounded coarse head-to-trunk proportion.",
                    "basis_fact_ids": ["coarse-structure"],
                    "confidence": "high",
                },
                {
                    "constraint_id": "paired-support-symmetry",
                    "category": "symmetry-orientation",
                    "mode": "hint",
                    "landmark_ids": ["support-left", "support-right", "trunk"],
                    "value_range": None,
                    "text": "Keep paired supports approximately bilateral around the trunk unless pose intent later says otherwise.",
                    "basis_fact_ids": ["coarse-structure"],
                    "confidence": "medium",
                },
                {
                    "constraint_id": "head-articulation",
                    "category": "articulation",
                    "mode": "required-range",
                    "landmark_ids": ["head", "trunk"],
                    "value_range": {"minimum": -45.0, "maximum": 45.0, "unit": "degrees"},
                    "text": "Keep the retained neutral head articulation inside the coarse fixture range.",
                    "basis_fact_ids": ["coarse-structure"],
                    "confidence": "medium",
                },
                {
                    "constraint_id": "head-silhouette",
                    "category": "silhouette-critical",
                    "mode": "hint",
                    "landmark_ids": ["head", "trunk"],
                    "value_range": None,
                    "text": "Preserve a visible head break from the trunk silhouette.",
                    "basis_fact_ids": ["coarse-structure"],
                    "confidence": "high",
                },
                {
                    "constraint_id": "paired-ground-contact",
                    "category": "support-contact",
                    "mode": "hint",
                    "landmark_ids": ["support-left", "support-right"],
                    "value_range": None,
                    "text": "Keep both declared support landmarks available to contact the coarse ground line.",
                    "basis_fact_ids": ["coarse-structure"],
                    "confidence": "high",
                },
                {
                    "constraint_id": "small-sprite-feature-tolerance",
                    "category": "resolution-stylization",
                    "mode": "stylization-tolerance",
                    "landmark_ids": ["head", "support-left", "support-right"],
                    "value_range": {"minimum": 0.0, "maximum": 2.0, "unit": "pixels"},
                    "text": "Silhouette-critical features may expand by up to two pixels at the target low resolution.",
                    "basis_fact_ids": ["low-resolution-readability"],
                    "confidence": "medium",
                },
            ],
        },
    }


class CreatureMorphologyProfileTests(unittest.TestCase):
    def test_simple_creature_profile_validates(self) -> None:
        profile = _profile()
        self.assertIs(profile, validate_simple_creature_morphology_profile(profile))

    def test_legacy_research_profile_remains_valid_but_is_not_promoted(self) -> None:
        profile = _profile()
        profile.pop("creature_structure")
        self.assertIs(profile, validate_morphology_profile(profile))
        with self.assertRaisesRegex(ResearchProfileValidationError, "missing_creature_structure"):
            validate_simple_creature_morphology_profile(profile)

    def test_landmark_references_fail_closed(self) -> None:
        profile = _profile()
        structure = profile["creature_structure"]
        assert type(structure) is dict
        constraints = structure["constraints"]
        assert type(constraints) is list and type(constraints[0]) is dict
        constraints[0]["landmark_ids"] = ["missing-landmark", "trunk"]
        with self.assertRaisesRegex(ResearchProfileValidationError, "unknown_landmark_reference"):
            validate_simple_creature_morphology_profile(profile)

    def test_required_ranges_are_finite_and_ordered(self) -> None:
        for minimum, maximum in ((float("nan"), 1.0), (2.0, 1.0)):
            profile = _profile()
            structure = profile["creature_structure"]
            assert type(structure) is dict
            constraints = structure["constraints"]
            assert type(constraints) is list and type(constraints[0]) is dict
            value_range = constraints[0]["value_range"]
            assert type(value_range) is dict
            value_range["minimum"] = minimum
            value_range["maximum"] = maximum
            with self.assertRaises(ResearchProfileValidationError):
                validate_simple_creature_morphology_profile(profile)

    def test_where_applicable_category_can_bind_an_explicit_unknown(self) -> None:
        profile = _profile()
        structure = profile["creature_structure"]
        assert type(structure) is dict
        declarations = structure["category_declarations"]
        constraints = structure["constraints"]
        assert type(declarations) is list and type(constraints) is list
        articulation = next(item for item in declarations if type(item) is dict and item.get("category") == "articulation")
        assert type(articulation) is dict
        articulation["status"] = "unknown"
        articulation["unknown_id"] = "exact-neck-axis"
        structure["constraints"] = [
            item
            for item in constraints
            if not (type(item) is dict and item.get("category") == "articulation")
        ]
        self.assertIs(profile, validate_simple_creature_morphology_profile(profile))

    def test_structure_changes_are_digest_visible(self) -> None:
        profile = _profile()
        digest = morphology_profile_sha256(profile)
        ref = {
            "profile_id": profile["profile_id"],
            "profile_schema": MORPHOLOGY_PROFILE_SCHEMA_V1,
            "sha256": digest,
        }
        self.assertIs(ref, validate_morphology_profile_reference(ref, profile))

        changed = deepcopy(profile)
        structure = changed["creature_structure"]
        assert type(structure) is dict
        constraints = structure["constraints"]
        assert type(constraints) is list and type(constraints[0]) is dict
        value_range = constraints[0]["value_range"]
        assert type(value_range) is dict
        value_range["maximum"] = 0.7
        self.assertNotEqual(digest, morphology_profile_sha256(changed))
        with self.assertRaisesRegex(ResearchProfileValidationError, "profile_digest_mismatch"):
            validate_morphology_profile_reference(ref, changed)


if __name__ == "__main__":
    unittest.main()
