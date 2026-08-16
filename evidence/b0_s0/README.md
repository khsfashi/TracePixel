# B0-S0 checkpoint and owner runner

This directory contains the provider-free CI checkpoint plus the owner-local entry points for the frozen B0 scored visible cohort and its preregistered blind human review.

- `checkpoint.py` proves the 28-attempt schedule, deterministic T0 scoring, matched method execution and hidden-constraint request separation without calling a provider.
- `run.py` performs the real owner-triggered cohort only after exact Codex CLI / ChatGPT-auth and frozen-source preflight checks.
- `review.py` validates the retained scored evidence and launches a loopback-only method-blind browser surface for the repository owner's frozen 1-5 perceptual ratings. It seals `owner-review.json` without method labels and writes a derived per-method summary only after the rating record is sealed.

The real run writes immutable attempt evidence under `evidence/b0/results/` and a method-neutral blind-review package under `evidence/b0/review/`. It never runs in portable GitHub-hosted CI.

Portable CI may run `python -m evidence.b0_s0.review --validate-package-only` to verify the retained bytes, manifest hashes, blind order, and any already-sealed owner review without invoking a provider or pretending to perform human evaluation.

See `docs/B0_SCORED_COHORT.md` before starting the real cohort and `docs/B0_OWNER_REVIEW.md` before recording the human review. Starting a real provider call begins the preregistered scored cohort; do not use it as a smoke test.
