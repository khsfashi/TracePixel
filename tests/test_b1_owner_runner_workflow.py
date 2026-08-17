from pathlib import Path


WORKFLOW = Path(".github/workflows/b1-owner-scored-cohort.yml")


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_b1_owner_runner_is_one_shot_self_hosted_only() -> None:
    text = _workflow()

    assert "owner/b1-s0-preflight-trigger" in text
    assert "owner/b1-s0-scored-trigger" in text
    assert "github.event.head_commit.message == 'Trigger B1-S0 owner preflight'" in text
    assert "github.event.head_commit.message == 'Trigger B1-S0 owner scored cohort'" in text
    assert "runs-on: [self-hosted, windows, x64, tracepixel-owner]" in text
    assert "pull_request:" not in text
    assert "workflow_dispatch:" not in text
    assert "cancel-in-progress: false" in text
    assert "cancel-in-progress: true" not in text


def test_b1_owner_runner_pins_exact_trigger_and_persists_claims_outside_checkout() -> None:
    text = _workflow()

    assert "ref: ${{ github.sha }}" in text
    assert "fetch-depth: 0" in text
    assert "$env:USERPROFILE" in text
    assert ".tracepixel\\b1-s0" in text
    assert "TRACEPIXEL_B1_RESULTS_ROOT=$resultsRoot" in text
    assert "TRACEPIXEL_B1_REVIEW_ROOT=$reviewRoot" in text
    assert "--results-root \"$env:TRACEPIXEL_B1_RESULTS_ROOT\"" in text
    assert "--review-root \"$env:TRACEPIXEL_B1_REVIEW_ROOT\"" in text


def test_b1_owner_runner_defers_auth_marker_enforcement_to_python_preflight() -> None:
    text = _workflow()

    assert "Verify owner Codex command surface" in text
    assert "codex login status" in text
    assert "$login =" not in text
    assert "Logged in using ChatGPT" not in text
    assert "python -m evidence.b1_s0.run --preflight-only" in text


def test_b1_owner_runner_preflights_before_scoring_and_publishes_only_complete_evidence() -> None:
    text = _workflow()

    preflight = text.index("python -m evidence.b1_s0.run --preflight-only")
    scored = text.index("--run-scored-cohort")
    publish = text.index("Publish retained evidence branch")

    assert preflight < scored < publish
    assert "Verify scored cohort completed without live claims" in text
    assert "git switch --detach $baseCommit" in text
    assert "evidence/b1-s0-${{ github.run_id }}" in text
