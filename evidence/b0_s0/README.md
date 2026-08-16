# B0-S0 checkpoint and owner runner

This directory contains the provider-free CI checkpoint plus the owner-local entry point for the frozen B0 scored visible cohort.

- `checkpoint.py` proves the 28-attempt schedule, deterministic T0 scoring, matched method execution and hidden-constraint request separation without calling a provider.
- `run.py` performs the real owner-triggered cohort only after exact Codex CLI / ChatGPT-auth and frozen-source preflight checks.

The real run writes immutable attempt evidence under `evidence/b0/results/` and a method-neutral blind-review package under `evidence/b0/review/`. It never runs in portable GitHub-hosted CI.

See `docs/B0_SCORED_COHORT.md` before starting the real cohort. Starting a real provider call begins the preregistered scored cohort; do not use it as a smoke test.
