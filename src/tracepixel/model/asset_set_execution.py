from __future__ import annotations

from typing import Literal, TypedDict

from .asset_set import AssetSetAggregateBudgetV1

ASSET_SET_MEMBER_EXECUTION_SCHEMA_V1 = "tracepixel.asset-set-member-execution.v1"
ASSET_SET_EXECUTION_REPORT_SCHEMA_V1 = "tracepixel.asset-set-execution-report.v1"

AssetSetMemberStatusV1 = Literal["succeeded", "failed", "budget_exhausted"]
AssetSetCacheDecisionV1 = Literal["executed", "reused"]
AssetSetBudgetDimensionV1 = Literal["provider_calls", "pixel_edits", "wall_time"]


class AssetSetMemberCacheV1(TypedDict):
    decision: AssetSetCacheDecisionV1
    source_request_sha256: str | None
    source_result_ref: str | None
    source_result_sha256: str | None


class AssetSetMemberEvidenceRefsV1(TypedDict):
    deterministic_qa_ref: str | None
    perceptual_ref: str | None
    complexity_ref: str | None
    provenance_ref: str | None


class AssetSetMemberExecutionV1(TypedDict):
    schema: Literal["tracepixel.asset-set-member-execution.v1"]
    ordinal: int
    member_id: str
    request_ref: str
    request_sha256: str
    status: AssetSetMemberStatusV1
    result_ref: str | None
    result_sha256: str | None
    provider_calls: int
    input_tokens: int | None
    output_tokens: int | None
    token_accounting_complete: bool
    pixel_edits: int
    retry_count: int
    retry_reasons: list[str]
    repair_count: int
    repair_reasons: list[str]
    cache: AssetSetMemberCacheV1
    wall_time_ns: int
    evidence_refs: AssetSetMemberEvidenceRefsV1
    failure_category: str | None
    failure_reason: str | None


class AssetSetExecutionReportV1(TypedDict):
    schema: Literal["tracepixel.asset-set-execution-report.v1"]
    asset_set_id: str
    asset_set_sha256: str
    request_sha256: str
    declared_max_concurrency: int
    observed_peak_live_members: int
    aggregate_budget: AssetSetAggregateBudgetV1
    aggregate_provider_calls: int
    aggregate_input_tokens: int | None
    aggregate_output_tokens: int | None
    token_accounting_complete: bool
    aggregate_pixel_edits: int
    aggregate_retry_count: int
    aggregate_repair_count: int
    batch_wall_time_ns: int
    scheduler_wall_time_ns: int
    scheduler_provider_calls: int
    scheduler_input_tokens: int
    scheduler_output_tokens: int
    budget_exhausted: list[AssetSetBudgetDimensionV1]
    failed_member_ids: list[str]
    members: list[AssetSetMemberExecutionV1]
