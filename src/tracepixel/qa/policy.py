from __future__ import annotations

from typing import Literal, TypedDict, cast

from tracepixel.qa.color import COLOR_QA_SCHEMA_V1, ColorQaV1
from tracepixel.qa.connectivity import CONNECTIVITY_QA_SCHEMA_V1, ConnectivityQaV1
from tracepixel.qa.shape_outline import SHAPE_OUTLINE_QA_SCHEMA_V1, ShapeOutlineQaV1
from tracepixel.qa.structural import STRUCTURAL_QA_SCHEMA_V1, StructuralFactsV1
from tracepixel.qa.tile_edge import TILE_EDGE_QA_SCHEMA_V1, TileEdgeQaV1

QA_POLICY_SCHEMA_V1 = "tracepixel.qa-policy.v1"
QA_FINDINGS_SCHEMA_V1 = "tracepixel.qa-findings.v1"

QaSeverityV1 = Literal["info", "warning", "error"]
QaCategoryV1 = Literal["structural", "color", "connectivity", "shape", "tile"]
QaRuleIdV1 = Literal[
    "structural.non_empty",
    "structural.no_translucency",
    "structural.no_edge_contact",
    "color.palette_membership",
    "color.maximum_colors",
    "color.transparent_rgb_policy",
    "connectivity.single_component",
    "connectivity.no_isolated_pixels",
    "shape.required_symmetry",
    "tile.contract",
]

_RULE_CATEGORY_BY_ID: dict[QaRuleIdV1, QaCategoryV1] = {
    "structural.non_empty": "structural",
    "structural.no_translucency": "structural",
    "structural.no_edge_contact": "structural",
    "color.palette_membership": "color",
    "color.maximum_colors": "color",
    "color.transparent_rgb_policy": "color",
    "connectivity.single_component": "connectivity",
    "connectivity.no_isolated_pixels": "connectivity",
    "shape.required_symmetry": "shape",
    "tile.contract": "tile",
}
_RULE_IDS = frozenset(_RULE_CATEGORY_BY_ID)
_SEVERITIES = frozenset(("info", "warning", "error"))
MAX_QA_POLICY_RULES_V1 = len(_RULE_CATEGORY_BY_ID)


class QaPolicyRuleV1(TypedDict):
    rule: QaRuleIdV1
    severity: QaSeverityV1


class QaPolicyV1(TypedDict):
    schema: Literal["tracepixel.qa-policy.v1"]
    rules: list[QaPolicyRuleV1]


class QaFindingV1(TypedDict):
    rule: QaRuleIdV1
    category: QaCategoryV1
    severity: QaSeverityV1


class QaFindingsV1(TypedDict):
    schema: Literal["tracepixel.qa-findings.v1"]
    findings: list[QaFindingV1]


class QaPolicyValidationError(ValueError):
    """Deterministic rejection for malformed explicit Q5 policy input."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


class QaPolicyEvaluationError(ValueError):
    """Deterministic rejection when a selected Q5 rule lacks its required Q0-Q4 fact/check."""

    def __init__(self, code: str, rule: QaRuleIdV1, message: str) -> None:
        self.code = code
        self.rule = rule
        self.message = message
        super().__init__(f"{rule}: {message} [{code}]")


def _fail_policy(code: str, path: str, message: str) -> None:
    raise QaPolicyValidationError(code, path, message)


def _require_exact_object(
    value: object,
    path: str,
    fields: frozenset[str],
) -> dict[str, object]:
    if type(value) is not dict:
        _fail_policy("invalid_type", path, "must be a JSON object")
    obj = cast(dict[object, object], value)
    if not all(type(key) is str for key in obj):
        _fail_policy("invalid_fields", path, "object keys must be strings")
    actual = frozenset(cast(dict[str, object], obj))
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail_policy("invalid_fields", path, "; ".join(parts))
    return cast(dict[str, object], obj)


def _require_exact_array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail_policy("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def validate_qa_policy(policy: object) -> QaPolicyV1:
    """Validate a closed ordered Q5 rule/severity policy without copying or normalization."""

    root = _require_exact_object(policy, "$", frozenset(("schema", "rules")))
    if root["schema"] != QA_POLICY_SCHEMA_V1:
        _fail_policy(
            "unsupported_schema",
            "$.schema",
            f"expected {QA_POLICY_SCHEMA_V1!r}",
        )

    rules = _require_exact_array(root["rules"], "$.rules")
    if len(rules) > MAX_QA_POLICY_RULES_V1:
        _fail_policy(
            "too_many_rules",
            "$.rules",
            f"policy supports at most {MAX_QA_POLICY_RULES_V1} unique rules",
        )

    seen: set[str] = set()
    for index, value in enumerate(rules):
        path = f"$.rules[{index}]"
        record = _require_exact_object(value, path, frozenset(("rule", "severity")))

        rule_value = record["rule"]
        if type(rule_value) is not str or rule_value not in _RULE_IDS:
            _fail_policy("unknown_rule", f"{path}.rule", "must be a supported Q5 rule id")
        rule = cast(QaRuleIdV1, rule_value)
        if rule in seen:
            _fail_policy("duplicate_rule", f"{path}.rule", f"duplicate rule {rule!r}")
        seen.add(rule)

        severity = record["severity"]
        if type(severity) is not str or severity not in _SEVERITIES:
            _fail_policy(
                "invalid_severity",
                f"{path}.severity",
                "must be 'info', 'warning', or 'error'",
            )

    return cast(QaPolicyV1, policy)


def _require_fact(
    value: object,
    *,
    expected_schema: str,
    source_name: str,
    rule: QaRuleIdV1,
) -> dict[str, object]:
    if type(value) is not dict or cast(dict[str, object], value).get("schema") != expected_schema:
        raise QaPolicyEvaluationError(
            "missing_or_invalid_fact",
            rule,
            f"requires {source_name} facts with schema {expected_schema!r}",
        )
    return cast(dict[str, object], value)


def _require_check(
    value: object,
    *,
    check_name: str,
    rule: QaRuleIdV1,
) -> dict[str, object]:
    if type(value) is not dict:
        raise QaPolicyEvaluationError(
            "missing_explicit_check",
            rule,
            f"requires upstream {check_name} to be explicitly configured",
        )
    return cast(dict[str, object], value)


def evaluate_qa_policy(
    policy: object,
    *,
    structural: StructuralFactsV1 | None = None,
    color: ColorQaV1 | None = None,
    connectivity: ConnectivityQaV1 | None = None,
    shape_outline: ShapeOutlineQaV1 | None = None,
    tile_edge: TileEdgeQaV1 | None = None,
) -> QaFindingsV1:
    """Evaluate only selected Q5 policy rules over already-computed Q0-Q4 facts.

    Q5 never reads Canvas state and never invokes a raster analyzer. Rule order is policy
    order, each failed rule emits at most one typed finding, and passing rules emit nothing.
    Explicit Q1/Q3/Q4 checks must already exist when their Q5 rule is selected so Q5 cannot
    silently invent palette limits, symmetry requirements, transparent-RGB rules or tiling
    requirements.
    """

    validated = validate_qa_policy(policy)
    findings: list[QaFindingV1] = []

    for policy_rule in validated["rules"]:
        rule = policy_rule["rule"]
        failed = False

        if rule == "structural.non_empty":
            facts = _require_fact(
                structural,
                expected_schema=STRUCTURAL_QA_SCHEMA_V1,
                source_name="structural",
                rule=rule,
            )
            failed = bool(facts["empty"])
        elif rule == "structural.no_translucency":
            facts = _require_fact(
                structural,
                expected_schema=STRUCTURAL_QA_SCHEMA_V1,
                source_name="structural",
                rule=rule,
            )
            alpha = cast(dict[str, object], facts["alpha"])
            failed = bool(alpha["has_translucency"])
        elif rule == "structural.no_edge_contact":
            facts = _require_fact(
                structural,
                expected_schema=STRUCTURAL_QA_SCHEMA_V1,
                source_name="structural",
                rule=rule,
            )
            edge_contact = cast(dict[str, object], facts["edge_contact"])
            failed = bool(edge_contact["any"])
        elif rule == "color.palette_membership":
            facts = _require_fact(
                color,
                expected_schema=COLOR_QA_SCHEMA_V1,
                source_name="color",
                rule=rule,
            )
            check = _require_check(
                facts["palette_membership"],
                check_name="color.palette_membership",
                rule=rule,
            )
            failed = not bool(check["satisfied"])
        elif rule == "color.maximum_colors":
            facts = _require_fact(
                color,
                expected_schema=COLOR_QA_SCHEMA_V1,
                source_name="color",
                rule=rule,
            )
            check = _require_check(
                facts["maximum_colors"],
                check_name="color.maximum_colors",
                rule=rule,
            )
            failed = not bool(check["satisfied"])
        elif rule == "color.transparent_rgb_policy":
            facts = _require_fact(
                color,
                expected_schema=COLOR_QA_SCHEMA_V1,
                source_name="color",
                rule=rule,
            )
            check = _require_check(
                facts["transparent_rgb_policy"],
                check_name="color.transparent_rgb_policy",
                rule=rule,
            )
            failed = not bool(check["satisfied"])
        elif rule == "connectivity.single_component":
            facts = _require_fact(
                connectivity,
                expected_schema=CONNECTIVITY_QA_SCHEMA_V1,
                source_name="connectivity",
                rule=rule,
            )
            components = cast(dict[str, object], facts["components"])
            failed = components["count"] != 1
        elif rule == "connectivity.no_isolated_pixels":
            facts = _require_fact(
                connectivity,
                expected_schema=CONNECTIVITY_QA_SCHEMA_V1,
                source_name="connectivity",
                rule=rule,
            )
            isolated = cast(dict[str, object], facts["isolated_pixels"])
            failed = bool(isolated["has_isolated_pixels"])
        elif rule == "shape.required_symmetry":
            facts = _require_fact(
                shape_outline,
                expected_schema=SHAPE_OUTLINE_QA_SCHEMA_V1,
                source_name="shape_outline",
                rule=rule,
            )
            symmetry = _require_check(
                facts["symmetry"],
                check_name="shape.required_symmetry",
                rule=rule,
            )
            vertical = symmetry["vertical"]
            horizontal = symmetry["horizontal"]
            failed = (
                type(vertical) is dict and not bool(cast(dict[str, object], vertical)["matches"])
            ) or (
                type(horizontal) is dict
                and not bool(cast(dict[str, object], horizontal)["matches"])
            )
        else:
            facts = _require_fact(
                tile_edge,
                expected_schema=TILE_EDGE_QA_SCHEMA_V1,
                source_name="tile_edge",
                rule=rule,
            )
            check = _require_check(
                facts["contract"],
                check_name="tile.contract",
                rule=rule,
            )
            failed = not bool(check["satisfied"])

        if failed:
            findings.append(
                {
                    "rule": rule,
                    "category": _RULE_CATEGORY_BY_ID[rule],
                    "severity": policy_rule["severity"],
                }
            )

    return {"schema": QA_FINDINGS_SCHEMA_V1, "findings": findings}
