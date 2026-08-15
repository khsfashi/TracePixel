from __future__ import annotations

import copy
import unittest

from tracepixel.qa import (
    QA_FINDINGS_SCHEMA_V1,
    QA_POLICY_SCHEMA_V1,
    QaPolicyEvaluationError,
    QaPolicyValidationError,
    analyze_color,
    analyze_connectivity,
    analyze_shape_outline,
    analyze_structural,
    analyze_tile_edges,
    evaluate_qa_policy,
    validate_qa_policy,
)
from tracepixel.raster import Canvas


FULL_POLICY = {
    "schema": QA_POLICY_SCHEMA_V1,
    "rules": [
        {"rule": "structural.non_empty", "severity": "error"},
        {"rule": "structural.no_translucency", "severity": "warning"},
        {"rule": "structural.no_edge_contact", "severity": "warning"},
        {"rule": "color.palette_membership", "severity": "error"},
        {"rule": "color.maximum_colors", "severity": "error"},
        {"rule": "color.transparent_rgb_policy", "severity": "error"},
        {"rule": "connectivity.single_component", "severity": "error"},
        {"rule": "connectivity.no_isolated_pixels", "severity": "warning"},
        {"rule": "shape.required_symmetry", "severity": "error"},
        {"rule": "tile.contract", "severity": "error"},
    ],
}


def _analyze(canvas: Canvas, *, clean: bool) -> dict[str, object]:
    palette = [(20, 40, 200, 255)] if clean else [
        (200, 30, 30, 255),
        (20, 40, 200, 255),
    ]
    max_colors = 1 if clean else 2
    return {
        "structural": analyze_structural(canvas),
        "color": analyze_color(
            canvas,
            palette=palette,
            max_colors=max_colors,
            transparent_rgb_policy="require_zero",
        ),
        "connectivity": analyze_connectivity(canvas),
        "shape_outline": analyze_shape_outline(canvas, required_symmetry="vertical"),
        "tile_edge": analyze_tile_edges(
            canvas,
            required_edges="both",
            require_equal_corners=True,
        ),
    }


def _evaluate(policy: object, facts: dict[str, object]) -> object:
    return evaluate_qa_policy(
        policy,
        structural=facts["structural"],  # type: ignore[arg-type]
        color=facts["color"],  # type: ignore[arg-type]
        connectivity=facts["connectivity"],  # type: ignore[arg-type]
        shape_outline=facts["shape_outline"],  # type: ignore[arg-type]
        tile_edge=facts["tile_edge"],  # type: ignore[arg-type]
    )


class QaPolicyTests(unittest.TestCase):
    def test_clean_fixture_emits_no_findings(self) -> None:
        canvas = Canvas(5, 5)
        canvas.set_pixels(
            [
                (2, 1, (20, 40, 200, 255)),
                (2, 2, (20, 40, 200, 255)),
                (2, 3, (20, 40, 200, 255)),
            ]
        )

        result = _evaluate(FULL_POLICY, _analyze(canvas, clean=True))

        self.assertEqual(
            result,
            {"schema": QA_FINDINGS_SCHEMA_V1, "findings": []},
        )

    def test_seeded_defects_emit_stable_typed_findings_in_policy_order(self) -> None:
        canvas = Canvas(5, 5)
        canvas.set_pixels(
            [
                (0, 0, (200, 30, 30, 255)),
                (2, 1, (20, 40, 200, 255)),
                (2, 2, (20, 40, 200, 255)),
                (1, 2, (30, 200, 60, 128)),
                (4, 4, (9, 9, 9, 0)),
            ]
        )

        result = _evaluate(FULL_POLICY, _analyze(canvas, clean=False))

        self.assertEqual(
            result,
            {
                "schema": QA_FINDINGS_SCHEMA_V1,
                "findings": [
                    {
                        "rule": "structural.no_translucency",
                        "category": "structural",
                        "severity": "warning",
                    },
                    {
                        "rule": "structural.no_edge_contact",
                        "category": "structural",
                        "severity": "warning",
                    },
                    {
                        "rule": "color.palette_membership",
                        "category": "color",
                        "severity": "error",
                    },
                    {
                        "rule": "color.maximum_colors",
                        "category": "color",
                        "severity": "error",
                    },
                    {
                        "rule": "color.transparent_rgb_policy",
                        "category": "color",
                        "severity": "error",
                    },
                    {
                        "rule": "connectivity.single_component",
                        "category": "connectivity",
                        "severity": "error",
                    },
                    {
                        "rule": "connectivity.no_isolated_pixels",
                        "category": "connectivity",
                        "severity": "warning",
                    },
                    {
                        "rule": "shape.required_symmetry",
                        "category": "shape",
                        "severity": "error",
                    },
                    {
                        "rule": "tile.contract",
                        "category": "tile",
                        "severity": "error",
                    },
                ],
            },
        )

    def test_empty_policy_requires_no_fact_sources(self) -> None:
        result = evaluate_qa_policy({"schema": QA_POLICY_SCHEMA_V1, "rules": []})
        self.assertEqual(result, {"schema": QA_FINDINGS_SCHEMA_V1, "findings": []})

    def test_policy_validation_is_closed_and_rejects_duplicate_rules(self) -> None:
        cases = [
            (
                {"schema": QA_POLICY_SCHEMA_V1, "rules": [], "extra": True},
                "invalid_fields",
            ),
            (
                {"schema": "tracepixel.qa-policy.v2", "rules": []},
                "unsupported_schema",
            ),
            (
                {
                    "schema": QA_POLICY_SCHEMA_V1,
                    "rules": [{"rule": "style.pretty", "severity": "error"}],
                },
                "unknown_rule",
            ),
            (
                {
                    "schema": QA_POLICY_SCHEMA_V1,
                    "rules": [{"rule": "structural.non_empty", "severity": "fatal"}],
                },
                "invalid_severity",
            ),
            (
                {
                    "schema": QA_POLICY_SCHEMA_V1,
                    "rules": [
                        {"rule": "structural.non_empty", "severity": "error"},
                        {"rule": "structural.non_empty", "severity": "warning"},
                    ],
                },
                "duplicate_rule",
            ),
        ]

        for policy, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(QaPolicyValidationError) as caught:
                    validate_qa_policy(policy)
                self.assertEqual(caught.exception.code, code)

    def test_selected_rule_requires_the_corresponding_fact_schema(self) -> None:
        policy = {
            "schema": QA_POLICY_SCHEMA_V1,
            "rules": [{"rule": "structural.non_empty", "severity": "error"}],
        }

        with self.assertRaises(QaPolicyEvaluationError) as caught:
            evaluate_qa_policy(policy)
        self.assertEqual(caught.exception.code, "missing_or_invalid_fact")
        self.assertEqual(caught.exception.rule, "structural.non_empty")

        with self.assertRaises(QaPolicyEvaluationError) as caught:
            evaluate_qa_policy(
                policy,
                structural={"schema": "tracepixel.structural-qa.v999"},  # type: ignore[arg-type]
            )
        self.assertEqual(caught.exception.code, "missing_or_invalid_fact")

    def test_q1_q3_q4_rules_do_not_invent_missing_explicit_checks(self) -> None:
        canvas = Canvas(3, 3)
        cases = [
            (
                "color.maximum_colors",
                {"color": analyze_color(canvas)},
            ),
            (
                "shape.required_symmetry",
                {"shape_outline": analyze_shape_outline(canvas)},
            ),
            (
                "tile.contract",
                {"tile_edge": analyze_tile_edges(canvas)},
            ),
        ]

        for rule, kwargs in cases:
            with self.subTest(rule=rule):
                policy = {
                    "schema": QA_POLICY_SCHEMA_V1,
                    "rules": [{"rule": rule, "severity": "error"}],
                }
                with self.assertRaises(QaPolicyEvaluationError) as caught:
                    evaluate_qa_policy(policy, **kwargs)  # type: ignore[arg-type]
                self.assertEqual(caught.exception.code, "missing_explicit_check")

    def test_evaluation_is_reproducible_and_does_not_mutate_policy_or_facts(self) -> None:
        canvas = Canvas(5, 5)
        canvas.set_pixels(
            [
                (0, 0, (200, 30, 30, 255)),
                (2, 2, (20, 40, 200, 255)),
            ]
        )
        facts = _analyze(canvas, clean=False)
        policy = copy.deepcopy(FULL_POLICY)
        before_policy = copy.deepcopy(policy)
        before_facts = copy.deepcopy(facts)

        first = _evaluate(policy, facts)
        second = _evaluate(policy, facts)

        self.assertEqual(first, second)
        self.assertEqual(policy, before_policy)
        self.assertEqual(facts, before_facts)


if __name__ == "__main__":
    unittest.main()
