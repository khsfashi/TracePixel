from __future__ import annotations

from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from hashlib import sha256
from typing import Literal, TypedDict, cast

from tracepixel.model import (
    ArtIntentV1,
    ArtIntentValidationError,
    StageIdV1,
    STAGE_SEQUENCE_V1,
    validate_art_intent,
)
from tracepixel.qa import (
    MAX_QA_POLICY_RULES_V1,
    QA_FINDINGS_SCHEMA_V1,
    QaFindingsV1,
)

AGENT_OBSERVATION_SCHEMA_V1 = "tracepixel.agent-observation.v1"
MAX_AGENT_RECENT_REVISIONS_V1 = 4
MAX_AGENT_PREVIEW_BYTES_V1 = 64 * 1024

_AGENT_PROPOSAL_KINDS = frozenset(("pixel_program", "stage_plan"))
_QA_CATEGORIES = frozenset(("structural", "color", "connectivity", "shape", "tile"))
_QA_CATEGORY_BY_RULE = {
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
_QA_SEVERITIES = frozenset(("info", "warning", "error"))
_QA_RULES = frozenset(
    (
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
    )
)
_STAGE_IDS = frozenset(STAGE_SEQUENCE_V1)
_HEX_DIGITS = frozenset("0123456789abcdef")


class AgentCurrentContextV1(TypedDict):
    stage: StageIdV1 | None
    revision: int


class AgentRecentRevisionV1(TypedDict):
    revision: int
    stage: StageIdV1 | None
    proposal_kind: Literal["pixel_program", "stage_plan"]
    operation_count: int
    changed_pixels: int


class AgentPreviewObservationV1(TypedDict):
    media_type: Literal["image/png"]
    width: int
    height: int
    sha256: str
    data_base64: str


class AgentObservationV1(TypedDict):
    """Bounded provider-neutral state for one next-decision request."""

    schema: Literal["tracepixel.agent-observation.v1"]
    intent: ArtIntentV1
    current: AgentCurrentContextV1
    qa: QaFindingsV1
    preview: AgentPreviewObservationV1 | None
    recent: list[AgentRecentRevisionV1]


class AgentObservationContractError(ValueError):
    """Stable deterministic rejection for the compact-observation contract."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise AgentObservationContractError(code, path, message)


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
    typed = cast(dict[str, object], obj)
    actual = frozenset(typed)
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        _fail("invalid_fields", path, "; ".join(parts))
    return typed


def _require_nonnegative_int(value: object, path: str) -> int:
    if type(value) is not int:
        _fail("invalid_type", path, "must be an integer")
    integer = cast(int, value)
    if integer < 0:
        _fail("invalid_value", path, "must be >= 0")
    return integer


def _rebase(path: str, prefix: str) -> str:
    if path == "$":
        return prefix
    if path.startswith("$"):
        return f"{prefix}{path[1:]}"
    return prefix


def _validate_qa_findings(value: object) -> QaFindingsV1:
    root = _require_exact_object(value, "$.qa", frozenset(("schema", "findings")))
    if root["schema"] != QA_FINDINGS_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.qa.schema",
            f"expected {QA_FINDINGS_SCHEMA_V1!r}",
        )
    findings = root["findings"]
    if type(findings) is not list:
        _fail("invalid_type", "$.qa.findings", "must be a JSON array")
    finding_list = cast(list[object], findings)
    if len(finding_list) > MAX_QA_POLICY_RULES_V1:
        _fail(
            "too_many_findings",
            "$.qa.findings",
            f"supports at most {MAX_QA_POLICY_RULES_V1} deterministic findings",
        )

    seen_rules: set[str] = set()
    for index, item in enumerate(finding_list):
        path = f"$.qa.findings[{index}]"
        finding = _require_exact_object(
            item,
            path,
            frozenset(("rule", "category", "severity")),
        )
        rule = finding["rule"]
        category = finding["category"]
        severity = finding["severity"]
        if type(rule) is not str or rule not in _QA_RULES:
            _fail("invalid_qa_rule", f"{path}.rule", "must be a supported Q5 rule")
        if rule in seen_rules:
            _fail("duplicate_qa_rule", f"{path}.rule", f"duplicate rule {rule!r}")
        seen_rules.add(cast(str, rule))
        if type(category) is not str or category not in _QA_CATEGORIES:
            _fail("invalid_qa_category", f"{path}.category", "must be a supported Q5 category")
        if category != _QA_CATEGORY_BY_RULE[cast(str, rule)]:
            _fail("qa_category_mismatch", f"{path}.category", "must match the Q5 rule category")
        if type(severity) is not str or severity not in _QA_SEVERITIES:
            _fail("invalid_qa_severity", f"{path}.severity", "must be info, warning, or error")
    return cast(QaFindingsV1, value)


def _validate_preview(value: object) -> AgentPreviewObservationV1 | None:
    if value is None:
        return None
    preview = _require_exact_object(
        value,
        "$.preview",
        frozenset(("media_type", "width", "height", "sha256", "data_base64")),
    )
    if preview["media_type"] != "image/png":
        _fail("unsupported_preview_media_type", "$.preview.media_type", "must be 'image/png'")

    for field in ("width", "height"):
        dimension = preview[field]
        if type(dimension) is not int or cast(int, dimension) <= 0:
            _fail("invalid_preview_dimension", f"$.preview.{field}", "must be a positive integer")

    digest = preview["sha256"]
    if (
        type(digest) is not str
        or len(cast(str, digest)) != 64
        or any(char not in _HEX_DIGITS for char in cast(str, digest))
    ):
        _fail("invalid_preview_digest", "$.preview.sha256", "must be 64 lowercase hex characters")

    encoded = preview["data_base64"]
    if type(encoded) is not str:
        _fail("invalid_type", "$.preview.data_base64", "must be a base64 string")
    try:
        decoded = b64decode(cast(str, encoded), validate=True)
    except (Base64Error, ValueError):
        _fail("invalid_preview_base64", "$.preview.data_base64", "must be canonical base64 data")
    if len(decoded) > MAX_AGENT_PREVIEW_BYTES_V1:
        _fail(
            "preview_too_large",
            "$.preview.data_base64",
            f"decoded preview must be <= {MAX_AGENT_PREVIEW_BYTES_V1} bytes",
        )
    if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
        _fail("invalid_preview_png", "$.preview.data_base64", "must contain PNG signature bytes")
    if sha256(decoded).hexdigest() != digest:
        _fail("preview_digest_mismatch", "$.preview.sha256", "does not match preview bytes")
    return cast(AgentPreviewObservationV1, value)


def validate_agent_observation(observation: object) -> AgentObservationV1:
    """Validate bounded A1 state without raster access, provider state, or transcript history."""

    root = _require_exact_object(
        observation,
        "$",
        frozenset(("schema", "intent", "current", "qa", "preview", "recent")),
    )
    if root["schema"] != AGENT_OBSERVATION_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"expected {AGENT_OBSERVATION_SCHEMA_V1!r}",
        )

    try:
        validate_art_intent(root["intent"])
    except ArtIntentValidationError as exc:
        _fail(
            "invalid_intent",
            _rebase(exc.path, "$.intent"),
            f"ArtIntent validator rejected with {exc.code}: {exc.message}",
        )

    current = _require_exact_object(root["current"], "$.current", frozenset(("stage", "revision")))
    stage = current["stage"]
    if stage is not None and (type(stage) is not str or stage not in _STAGE_IDS):
        _fail("invalid_stage", "$.current.stage", "must be null or a supported P3 stage id")
    current_revision = _require_nonnegative_int(current["revision"], "$.current.revision")

    _validate_qa_findings(root["qa"])
    _validate_preview(root["preview"])

    recent = root["recent"]
    if type(recent) is not list:
        _fail("invalid_type", "$.recent", "must be a JSON array")
    recent_list = cast(list[object], recent)
    if len(recent_list) > MAX_AGENT_RECENT_REVISIONS_V1:
        _fail(
            "recent_context_too_large",
            "$.recent",
            f"must contain at most {MAX_AGENT_RECENT_REVISIONS_V1} records",
        )

    previous_revision = -1
    for index, item in enumerate(recent_list):
        path = f"$.recent[{index}]"
        record = _require_exact_object(
            item,
            path,
            frozenset(("revision", "stage", "proposal_kind", "operation_count", "changed_pixels")),
        )
        revision = _require_nonnegative_int(record["revision"], f"{path}.revision")
        if revision <= previous_revision:
            _fail("invalid_recent_order", f"{path}.revision", "revisions must be strictly increasing")
        if revision >= current_revision:
            _fail("invalid_recent_revision", f"{path}.revision", "must be less than current revision")
        previous_revision = revision

        record_stage = record["stage"]
        if record_stage is not None and (
            type(record_stage) is not str or record_stage not in _STAGE_IDS
        ):
            _fail("invalid_stage", f"{path}.stage", "must be null or a supported P3 stage id")
        proposal_kind = record["proposal_kind"]
        if type(proposal_kind) is not str or proposal_kind not in _AGENT_PROPOSAL_KINDS:
            _fail(
                "invalid_proposal_kind",
                f"{path}.proposal_kind",
                "must be 'pixel_program' or 'stage_plan'",
            )
        _require_nonnegative_int(record["operation_count"], f"{path}.operation_count")
        _require_nonnegative_int(record["changed_pixels"], f"{path}.changed_pixels")

    return cast(AgentObservationV1, observation)


def build_agent_observation(
    *,
    art_intent: ArtIntentV1,
    current_stage: StageIdV1 | None,
    revision: int,
    qa_findings: QaFindingsV1,
    recent: list[AgentRecentRevisionV1] | tuple[AgentRecentRevisionV1, ...] = (),
    preview_png: bytes | None = None,
    preview_width: int | None = None,
    preview_height: int | None = None,
) -> AgentObservationV1:
    """Build one compact observation from bounded deterministic summaries.

    The builder intentionally accepts no Canvas and no transcript. Preview bytes are opt-in and
    size-bounded; normal calls expose only ArtIntent, typed Q5 findings, current stage/revision,
    and at most four recent revision summaries.
    """

    validate_art_intent(art_intent)
    _validate_qa_findings(qa_findings)

    if preview_png is None:
        if preview_width is not None or preview_height is not None:
            _fail(
                "missing_preview_bytes",
                "$.preview",
                "preview dimensions require preview_png bytes",
            )
        preview: AgentPreviewObservationV1 | None = None
    else:
        if type(preview_png) is not bytes:
            _fail("invalid_type", "$.preview", "preview_png must be bytes")
        if len(preview_png) > MAX_AGENT_PREVIEW_BYTES_V1:
            _fail(
                "preview_too_large",
                "$.preview",
                f"preview_png must be <= {MAX_AGENT_PREVIEW_BYTES_V1} bytes",
            )
        if type(preview_width) is not int or preview_width <= 0:
            _fail("invalid_preview_dimension", "$.preview.width", "must be a positive integer")
        if type(preview_height) is not int or preview_height <= 0:
            _fail("invalid_preview_dimension", "$.preview.height", "must be a positive integer")
        preview = {
            "media_type": "image/png",
            "width": preview_width,
            "height": preview_height,
            "sha256": sha256(preview_png).hexdigest(),
            "data_base64": b64encode(preview_png).decode("ascii"),
        }

    intent_copy = cast(ArtIntentV1, {
        "schema": art_intent["schema"],
        "asset_class": art_intent["asset_class"],
        "canvas": dict(art_intent["canvas"]),
        "composition": {
            "occupied_bounds": (
                None
                if art_intent["composition"]["occupied_bounds"] is None
                else dict(art_intent["composition"]["occupied_bounds"])
            ),
            "facing": art_intent["composition"]["facing"],
            "symmetry": (
                None
                if art_intent["composition"]["symmetry"] is None
                else dict(art_intent["composition"]["symmetry"])
            ),
            "light_direction": art_intent["composition"]["light_direction"],
            "palette_budget": art_intent["composition"]["palette_budget"],
        },
    })
    qa_copy = cast(QaFindingsV1, {
        "schema": qa_findings["schema"],
        "findings": [dict(finding) for finding in qa_findings["findings"]],
    })
    recent_copy = [cast(AgentRecentRevisionV1, dict(record)) for record in recent]

    observation: AgentObservationV1 = {
        "schema": AGENT_OBSERVATION_SCHEMA_V1,
        "intent": intent_copy,
        "current": {"stage": current_stage, "revision": revision},
        "qa": qa_copy,
        "preview": preview,
        "recent": recent_copy,
    }
    return validate_agent_observation(observation)
