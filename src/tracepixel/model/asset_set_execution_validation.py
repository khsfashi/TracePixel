from __future__ import annotations

from typing import cast

from .asset_set_execution import (
    ASSET_SET_EXECUTION_REPORT_SCHEMA_V1,
    ASSET_SET_MEMBER_EXECUTION_SCHEMA_V1,
    AssetSetExecutionReportV1,
)
from .asset_set_schedule import AssetSetScheduleV1

_REPORT_FIELDS = frozenset(
    (
        "schema",
        "asset_set_id",
        "asset_set_sha256",
        "request_sha256",
        "declared_max_concurrency",
        "observed_peak_live_members",
        "aggregate_budget",
        "aggregate_provider_calls",
        "aggregate_input_tokens",
        "aggregate_output_tokens",
        "token_accounting_complete",
        "aggregate_pixel_edits",
        "aggregate_retry_count",
        "aggregate_repair_count",
        "batch_wall_time_ns",
        "scheduler_wall_time_ns",
        "scheduler_provider_calls",
        "scheduler_input_tokens",
        "scheduler_output_tokens",
        "budget_exhausted",
        "failed_member_ids",
        "members",
    )
)
_MEMBER_FIELDS = frozenset(
    (
        "schema",
        "ordinal",
        "member_id",
        "request_ref",
        "request_sha256",
        "status",
        "result_ref",
        "result_sha256",
        "provider_calls",
        "input_tokens",
        "output_tokens",
        "token_accounting_complete",
        "pixel_edits",
        "retry_count",
        "retry_reasons",
        "repair_count",
        "repair_reasons",
        "cache",
        "wall_time_ns",
        "evidence_refs",
        "failure_category",
        "failure_reason",
    )
)
_BUDGET_FIELDS = frozenset(("max_provider_calls", "max_pixel_edits", "max_wall_time_ms"))
_CACHE_FIELDS = frozenset(
    ("decision", "source_request_sha256", "source_result_ref", "source_result_sha256")
)
_EVIDENCE_FIELDS = frozenset(
    ("deterministic_qa_ref", "perceptual_ref", "complexity_ref", "provenance_ref")
)
_STATUSES = frozenset(("succeeded", "failed", "budget_exhausted"))
_BUDGET_DIMENSIONS = ("provider_calls", "pixel_edits", "wall_time")


class AssetSetExecutionValidationError(ValueError):
    """Deterministic rejection for retained P8-B1 execution evidence."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message} [{code}]")


def _fail(code: str, path: str, message: str) -> None:
    raise AssetSetExecutionValidationError(code, path, message)


def _object(value: object, path: str, fields: frozenset[str]) -> dict[str, object]:
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


def _nonnegative_int(value: object, path: str) -> int:
    if type(value) is not int or cast(int, value) < 0:
        _fail("invalid_integer", path, "must be a non-negative integer")
    return cast(int, value)


def _optional_nonnegative_int(value: object, path: str) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(value, path)


def _bool(value: object, path: str) -> bool:
    if type(value) is not bool:
        _fail("invalid_type", path, "must be a boolean")
    return cast(bool, value)


def _text_or_none(value: object, path: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not cast(str, value):
        _fail("invalid_text", path, "must be a non-empty string or null")
    return cast(str, value)


def _sha256_or_none(value: object, path: str) -> str | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or len(cast(str, value)) != 64
        or any(character not in "0123456789abcdef" for character in cast(str, value))
    ):
        _fail("invalid_digest", path, "must be 64 lowercase hexadecimal characters or null")
    return cast(str, value)


def _string_list(value: object, path: str) -> list[str]:
    if type(value) is not list:
        _fail("invalid_type", path, "must be a JSON array")
    result: list[str] = []
    for index, raw in enumerate(cast(list[object], value)):
        text = _text_or_none(raw, f"{path}[{index}]")
        if text is None or len(text) > 256:
            _fail("invalid_reason", f"{path}[{index}]", "must be a non-empty string <= 256 chars")
        result.append(text)
    return result


def validate_asset_set_execution_report(
    value: object,
    schedule: AssetSetScheduleV1,
) -> AssetSetExecutionReportV1:
    """Validate exact member retention and P8-C0-ready accounting invariants."""

    root = _object(value, "$", _REPORT_FIELDS)
    if root["schema"] != ASSET_SET_EXECUTION_REPORT_SCHEMA_V1:
        _fail(
            "unsupported_schema",
            "$.schema",
            f"expected {ASSET_SET_EXECUTION_REPORT_SCHEMA_V1!r}",
        )

    for field in ("asset_set_id", "asset_set_sha256", "request_sha256"):
        if root[field] != schedule[field]:
            _fail("schedule_mismatch", f"$.{field}", "must match the validated P8-B0 schedule")

    declared = _nonnegative_int(root["declared_max_concurrency"], "$.declared_max_concurrency")
    if declared != schedule["max_concurrency"]:
        _fail(
            "schedule_mismatch",
            "$.declared_max_concurrency",
            "must match schedule max_concurrency",
        )
    peak = _nonnegative_int(root["observed_peak_live_members"], "$.observed_peak_live_members")
    if peak > declared:
        _fail(
            "concurrency_exceeded",
            "$.observed_peak_live_members",
            "must not exceed declared max_concurrency",
        )

    budget = _object(root["aggregate_budget"], "$.aggregate_budget", _BUDGET_FIELDS)
    if budget != schedule["aggregate_budget"]:
        _fail("schedule_mismatch", "$.aggregate_budget", "must exactly match schedule budget")

    for field in (
        "aggregate_provider_calls",
        "aggregate_pixel_edits",
        "aggregate_retry_count",
        "aggregate_repair_count",
        "batch_wall_time_ns",
        "scheduler_wall_time_ns",
        "scheduler_provider_calls",
        "scheduler_input_tokens",
        "scheduler_output_tokens",
    ):
        _nonnegative_int(root[field], f"$.{field}")

    aggregate_input_tokens = _optional_nonnegative_int(
        root["aggregate_input_tokens"],
        "$.aggregate_input_tokens",
    )
    aggregate_output_tokens = _optional_nonnegative_int(
        root["aggregate_output_tokens"],
        "$.aggregate_output_tokens",
    )
    token_accounting_complete = _bool(
        root["token_accounting_complete"],
        "$.token_accounting_complete",
    )

    if any(
        root[field] != 0
        for field in (
            "scheduler_provider_calls",
            "scheduler_input_tokens",
            "scheduler_output_tokens",
        )
    ):
        _fail(
            "scheduler_provider_work",
            "$",
            "P8-B1 scheduler provider calls/tokens must be exactly zero before P8-B2",
        )

    exhausted_raw = root["budget_exhausted"]
    if type(exhausted_raw) is not list:
        _fail("invalid_type", "$.budget_exhausted", "must be a JSON array")
    exhausted = cast(list[object], exhausted_raw)
    if exhausted != [dimension for dimension in _BUDGET_DIMENSIONS if dimension in exhausted]:
        _fail(
            "invalid_budget_exhaustion",
            "$.budget_exhausted",
            "must be unique and ordered provider_calls, pixel_edits, wall_time",
        )
    if any(dimension not in _BUDGET_DIMENSIONS for dimension in exhausted):
        _fail("invalid_budget_exhaustion", "$.budget_exhausted", "contains unknown dimension")

    raw_members = root["members"]
    if type(raw_members) is not list:
        _fail("invalid_type", "$.members", "must be a JSON array")
    members = cast(list[object], raw_members)
    scheduled = schedule["members"]
    if len(members) != len(scheduled):
        _fail("member_count_mismatch", "$.members", "must retain every scheduled member exactly once")

    provider_sum = 0
    input_sum = 0
    output_sum = 0
    pixel_sum = 0
    retry_sum = 0
    repair_sum = 0
    derived_failed: list[str] = []

    for index, (raw, expected) in enumerate(zip(members, scheduled, strict=True)):
        path = f"$.members[{index}]"
        member = _object(raw, path, _MEMBER_FIELDS)
        if member["schema"] != ASSET_SET_MEMBER_EXECUTION_SCHEMA_V1:
            _fail(
                "unsupported_schema",
                f"{path}.schema",
                f"expected {ASSET_SET_MEMBER_EXECUTION_SCHEMA_V1!r}",
            )
        for field in ("ordinal", "member_id", "request_ref", "request_sha256"):
            if member[field] != expected[field]:
                _fail("member_identity_mismatch", f"{path}.{field}", "must match scheduled identity")

        status = member["status"]
        if type(status) is not str or status not in _STATUSES:
            _fail("invalid_status", f"{path}.status", f"must be one of {sorted(_STATUSES)}")

        result_ref = _text_or_none(member["result_ref"], f"{path}.result_ref")
        result_sha = _sha256_or_none(member["result_sha256"], f"{path}.result_sha256")
        failure_category = _text_or_none(member["failure_category"], f"{path}.failure_category")
        failure_reason = _text_or_none(member["failure_reason"], f"{path}.failure_reason")
        if status == "succeeded":
            if result_ref is None or result_sha is None:
                _fail("missing_result", path, "successful member must retain immutable result identity")
            if failure_category is not None or failure_reason is not None:
                _fail("invalid_failure", path, "successful member cannot carry failure fields")
        else:
            derived_failed.append(cast(str, member["member_id"]))
            if result_ref is not None or result_sha is not None:
                _fail("invalid_result", path, "failed/budget-exhausted member cannot claim result identity")
            if failure_category is None or failure_reason is None:
                _fail("missing_failure", path, "failed/budget-exhausted member must retain failure reason")

        provider_calls = _nonnegative_int(member["provider_calls"], f"{path}.provider_calls")
        input_tokens = _optional_nonnegative_int(member["input_tokens"], f"{path}.input_tokens")
        output_tokens = _optional_nonnegative_int(member["output_tokens"], f"{path}.output_tokens")
        member_tokens_complete = _bool(
            member["token_accounting_complete"],
            f"{path}.token_accounting_complete",
        )
        if member_tokens_complete:
            if input_tokens is None or output_tokens is None:
                _fail(
                    "incomplete_token_accounting",
                    path,
                    "complete member token accounting requires exact input/output counts",
                )
        elif input_tokens is not None or output_tokens is not None:
            _fail(
                "partial_token_accounting",
                path,
                "incomplete member token accounting must use null input/output totals",
            )
        pixel_edits = _nonnegative_int(member["pixel_edits"], f"{path}.pixel_edits")
        retry_count = _nonnegative_int(member["retry_count"], f"{path}.retry_count")
        repair_count = _nonnegative_int(member["repair_count"], f"{path}.repair_count")
        _nonnegative_int(member["wall_time_ns"], f"{path}.wall_time_ns")
        retry_reasons = _string_list(member["retry_reasons"], f"{path}.retry_reasons")
        repair_reasons = _string_list(member["repair_reasons"], f"{path}.repair_reasons")
        if retry_count != len(retry_reasons):
            _fail("count_mismatch", f"{path}.retry_count", "must equal retained retry reasons")
        if repair_count != len(repair_reasons):
            _fail("count_mismatch", f"{path}.repair_count", "must equal retained repair reasons")

        cache = _object(member["cache"], f"{path}.cache", _CACHE_FIELDS)
        decision = cache["decision"]
        if type(decision) is not str or decision not in ("executed", "reused"):
            _fail("invalid_cache_decision", f"{path}.cache.decision", "must be executed or reused")
        source_request = _sha256_or_none(
            cache["source_request_sha256"],
            f"{path}.cache.source_request_sha256",
        )
        source_result_ref = _text_or_none(
            cache["source_result_ref"],
            f"{path}.cache.source_result_ref",
        )
        source_result_sha = _sha256_or_none(
            cache["source_result_sha256"],
            f"{path}.cache.source_result_sha256",
        )
        if decision == "reused":
            if status != "succeeded":
                _fail("invalid_cache_reuse", path, "only successful members may be reused")
            if source_request is None or source_result_ref is None or source_result_sha is None:
                _fail("missing_cache_source", f"{path}.cache", "reused member needs immutable source identity")
            if (
                provider_calls
                or input_tokens not in (0, None)
                or output_tokens not in (0, None)
                or pixel_edits
            ):
                _fail(
                    "reused_member_cost",
                    path,
                    "reused member must retain zero new provider/token/pixel work",
                )
        elif any(value is not None for value in (source_request, source_result_ref, source_result_sha)):
            _fail("unexpected_cache_source", f"{path}.cache", "executed member cannot claim reuse source")

        evidence = _object(member["evidence_refs"], f"{path}.evidence_refs", _EVIDENCE_FIELDS)
        for field, ref in evidence.items():
            _text_or_none(ref, f"{path}.evidence_refs.{field}")

        provider_sum += provider_calls
        if input_tokens is not None:
            input_sum += input_tokens
        if output_tokens is not None:
            output_sum += output_tokens
        pixel_sum += pixel_edits
        retry_sum += retry_count
        repair_sum += repair_count

    scheduler_provider = cast(int, root["scheduler_provider_calls"])
    scheduler_input = cast(int, root["scheduler_input_tokens"])
    scheduler_output = cast(int, root["scheduler_output_tokens"])
    expected_totals = {
        "aggregate_provider_calls": provider_sum + scheduler_provider,
        "aggregate_pixel_edits": pixel_sum,
        "aggregate_retry_count": retry_sum,
        "aggregate_repair_count": repair_sum,
    }
    for field, expected in expected_totals.items():
        if root[field] != expected:
            _fail("aggregate_mismatch", f"$.{field}", f"expected exact retained sum {expected}")

    members_tokens_complete = all(
        cast(dict[str, object], member)["token_accounting_complete"]
        for member in members
    )
    if token_accounting_complete != members_tokens_complete:
        _fail(
            "token_accounting_mismatch",
            "$.token_accounting_complete",
            "must be true iff every member has exact token accounting",
        )
    if token_accounting_complete:
        if aggregate_input_tokens != input_sum + scheduler_input:
            _fail(
                "aggregate_mismatch",
                "$.aggregate_input_tokens",
                f"expected exact retained sum {input_sum + scheduler_input}",
            )
        if aggregate_output_tokens != output_sum + scheduler_output:
            _fail(
                "aggregate_mismatch",
                "$.aggregate_output_tokens",
                f"expected exact retained sum {output_sum + scheduler_output}",
            )
    elif aggregate_input_tokens is not None or aggregate_output_tokens is not None:
        _fail(
            "partial_token_accounting",
            "$",
            "incomplete aggregate token accounting must use null input/output totals",
        )

    if provider_sum > schedule["aggregate_budget"]["max_provider_calls"]:
        _fail("provider_budget_exceeded", "$.aggregate_provider_calls", "exceeds aggregate budget")
    if pixel_sum > schedule["aggregate_budget"]["max_pixel_edits"]:
        _fail("pixel_budget_exceeded", "$.aggregate_pixel_edits", "exceeds aggregate budget")

    failed_raw = root["failed_member_ids"]
    if type(failed_raw) is not list or any(type(item) is not str for item in cast(list[object], failed_raw)):
        _fail("invalid_failed_members", "$.failed_member_ids", "must be a string array")
    if cast(list[str], failed_raw) != derived_failed:
        _fail(
            "failed_member_mismatch",
            "$.failed_member_ids",
            "must exactly list non-success members in declared order",
        )

    return cast(AssetSetExecutionReportV1, value)
