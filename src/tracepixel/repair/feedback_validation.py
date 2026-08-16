from __future__ import annotations

from typing import cast

from tracepixel.model.stage_plan import STAGE_SEQUENCE_V1
from tracepixel.qa import QaCategoryV1, QaRuleIdV1
from tracepixel.raster.contract import CanvasSizeError, CanvasSpec

from .feedback import (
    FEEDBACK_INTAKE_SCHEMA_V1,
    MAX_FEEDBACK_ITEMS_V1,
    MAX_FEEDBACK_TEXT_CHARS_V1,
    FeedbackIntakeV1,
)

_ROOT_FIELDS = frozenset(("schema", "target", "items"))
_TARGET_FIELDS = frozenset(("asset_id", "task_id", "canvas", "artifact_sha256"))
_CANVAS_FIELDS = frozenset(("width", "height"))
_ITEM_FIELDS = frozenset(
    (
        "id",
        "authority",
        "source_ref",
        "summary",
        "stage_hint",
        "region_hint",
        "deterministic_qa",
        "human",
    )
)
_REGION_FIELDS = frozenset(("x", "y", "width", "height"))
_QA_FIELDS = frozenset(("rule", "category", "severity"))
_HUMAN_FIELDS = frozenset(("human_rejection", "scores"))
_SCORE_FIELDS = frozenset(("dimension", "value"))

_AUTHORITIES = frozenset(("deterministic_qa", "owner_human"))
_STAGES = frozenset(STAGE_SEQUENCE_V1)
_SEVERITIES = frozenset(("info", "warning", "error"))
_SCORE_DIMENSIONS = frozenset(
    ("recognizability", "native_1x_readability", "style_coherence")
)
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


class FeedbackIntakeValidationError(ValueError):
    """Deterministic P7-F0 rejection with stable code and JSON-style path."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise FeedbackIntakeValidationError(code, path, message)


def _require_exact_object(
    value: object,
    path: str,
    fields: frozenset[str],
) -> dict[str, object]:
    if type(value) is not dict:
        _fail("invalid_type", path, "must be a JSON object")
    obj = cast(dict[object, object], value)
    if not all(type(key) is str for key in obj):
        _fail("invalid_fields", path, "object keys must be strings")
    actual = frozenset(cast(dict[str, object], obj))
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail("invalid_fields", path, "; ".join(parts))
    return cast(dict[str, object], obj)


def _require_array(value: object, path: str) -> list[object]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    return cast(list[object], value)


def _require_bounded_text(value: object, path: str, *, maximum: int) -> str:
    if type(value) is not str:
        _fail("invalid_type", path, "must be a string")
    text = cast(str, value)
    if not 1 <= len(text) <= maximum or not text.strip():
        _fail("invalid_text", path, f"must contain 1..{maximum} characters and not be blank")
    return text


def _validate_sha256(value: object, path: str) -> None:
    if value is None:
        return
    if type(value) is not str:
        _fail("invalid_type", path, "must be a lowercase SHA-256 string or null")
    digest = cast(str, value)
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        _fail("invalid_sha256", path, "must be exactly 64 lowercase hexadecimal characters")


def _validate_region(value: object, path: str, spec: CanvasSpec) -> None:
    if value is None:
        return
    region = _require_exact_object(value, path, _REGION_FIELDS)
    parts = (region["x"], region["y"], region["width"], region["height"])
    if not all(type(part) is int for part in parts):
        _fail("invalid_region", path, "x, y, width and height must be exact integers")
    x, y, width, height = cast(tuple[int, int, int, int], parts)
    if x < 0 or y < 0 or width < 1 or height < 1:
        _fail("invalid_region", path, "x/y must be non-negative and width/height positive")
    if x + width > spec.width or y + height > spec.height:
        _fail("invalid_region", path, "region hint must fit inside target canvas")


def _validate_deterministic(value: object, path: str) -> None:
    qa = _require_exact_object(value, path, _QA_FIELDS)
    rule = qa["rule"]
    category = qa["category"]
    severity = qa["severity"]
    if type(rule) is not str or rule not in _RULE_CATEGORY_BY_ID:
        _fail("invalid_qa_rule", f"{path}.rule", f"unsupported QA rule {rule!r}")
    expected_category = _RULE_CATEGORY_BY_ID[cast(QaRuleIdV1, rule)]
    if type(category) is not str or category != expected_category:
        _fail(
            "qa_category_mismatch",
            f"{path}.category",
            f"rule {rule!r} requires category {expected_category!r}",
        )
    if type(severity) is not str or severity not in _SEVERITIES:
        _fail("invalid_qa_severity", f"{path}.severity", f"unsupported severity {severity!r}")


def _validate_human(value: object, path: str) -> None:
    human = _require_exact_object(value, path, _HUMAN_FIELDS)
    rejection = human["human_rejection"]
    if rejection is not None and type(rejection) is not bool:
        _fail("invalid_type", f"{path}.human_rejection", "must be a boolean or null")

    scores = _require_array(human["scores"], f"{path}.scores")
    if len(scores) > len(_SCORE_DIMENSIONS):
        _fail(
            "too_many_scores",
            f"{path}.scores",
            f"at most {len(_SCORE_DIMENSIONS)} owner score dimensions are supported",
        )
    seen: set[str] = set()
    for index, raw_score in enumerate(scores):
        score_path = f"{path}.scores[{index}]"
        score = _require_exact_object(raw_score, score_path, _SCORE_FIELDS)
        dimension = score["dimension"]
        value_obj = score["value"]
        if type(dimension) is not str or dimension not in _SCORE_DIMENSIONS:
            _fail(
                "invalid_score_dimension",
                f"{score_path}.dimension",
                f"unsupported owner score dimension {dimension!r}",
            )
        if dimension in seen:
            _fail("duplicate_score_dimension", f"{score_path}.dimension", "dimension must be unique")
        seen.add(cast(str, dimension))
        if type(value_obj) is not int or not 1 <= value_obj <= 5:
            _fail("invalid_score", f"{score_path}.value", "must be an exact integer in [1, 5]")


def validate_feedback_intake(value: object) -> FeedbackIntakeV1:
    """Validate bounded P7-F0 intake without converting human judgment into QA truth."""

    root = _require_exact_object(value, "$", _ROOT_FIELDS)
    schema = root["schema"]
    if type(schema) is not str:
        _fail("invalid_type", "$.schema", "must be a string")
    if schema != FEEDBACK_INTAKE_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"unsupported schema {schema!r}; expected {FEEDBACK_INTAKE_SCHEMA_V1!r}",
        )

    target = _require_exact_object(root["target"], "$.target", _TARGET_FIELDS)
    _require_bounded_text(target["asset_id"], "$.target.asset_id", maximum=128)
    _require_bounded_text(target["task_id"], "$.target.task_id", maximum=128)
    canvas = _require_exact_object(target["canvas"], "$.target.canvas", _CANVAS_FIELDS)
    try:
        spec = CanvasSpec(canvas["width"], canvas["height"])
    except CanvasSizeError as exc:
        _fail("invalid_canvas", "$.target.canvas", str(exc))
    _validate_sha256(target["artifact_sha256"], "$.target.artifact_sha256")

    items = _require_array(root["items"], "$.items")
    if not 1 <= len(items) <= MAX_FEEDBACK_ITEMS_V1:
        _fail(
            "invalid_item_count",
            "$.items",
            f"must contain 1..{MAX_FEEDBACK_ITEMS_V1} feedback items",
        )

    seen_ids: set[str] = set()
    for index, raw_item in enumerate(items):
        path = f"$.items[{index}]"
        item = _require_exact_object(raw_item, path, _ITEM_FIELDS)
        item_id = _require_bounded_text(item["id"], f"{path}.id", maximum=64)
        if item_id in seen_ids:
            _fail("duplicate_item_id", f"{path}.id", "feedback item id must be unique")
        seen_ids.add(item_id)

        authority = item["authority"]
        if type(authority) is not str or authority not in _AUTHORITIES:
            _fail("invalid_authority", f"{path}.authority", f"unsupported authority {authority!r}")
        _require_bounded_text(item["source_ref"], f"{path}.source_ref", maximum=128)
        _require_bounded_text(
            item["summary"],
            f"{path}.summary",
            maximum=MAX_FEEDBACK_TEXT_CHARS_V1,
        )

        stage_hint = item["stage_hint"]
        if stage_hint is not None and (type(stage_hint) is not str or stage_hint not in _STAGES):
            _fail("invalid_stage_hint", f"{path}.stage_hint", f"unsupported stage {stage_hint!r}")
        _validate_region(item["region_hint"], f"{path}.region_hint", spec)

        deterministic = item["deterministic_qa"]
        human = item["human"]
        if authority == "deterministic_qa":
            if deterministic is None or human is not None:
                _fail(
                    "authority_payload_mismatch",
                    path,
                    "deterministic_qa requires deterministic_qa payload and null human payload",
                )
            _validate_deterministic(deterministic, f"{path}.deterministic_qa")
        else:
            if human is None or deterministic is not None:
                _fail(
                    "authority_payload_mismatch",
                    path,
                    "owner_human requires human payload and null deterministic_qa payload",
                )
            _validate_human(human, f"{path}.human")

    return cast(FeedbackIntakeV1, value)
