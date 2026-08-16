# P7-F1 Feedback Localization

P7-F1 turns each validated `tracepixel.feedback-intake.v1` item into an explicit, bounded stage/region scope for later repair planning. It does **not** create a repair PixelProgram, re-execute the asset, count changed pixels, or convert owner perception into deterministic QA.

## Contract

`tracepixel.feedback-localization.v1` contains:

- the exact validated F0 `intake`,
- one `localizations` entry for every intake item, in the same order,
- a non-empty canonical `affected_stages` scope,
- one top-left, half-open `affected_region`,
- explicit `stage_basis` and `region_basis` provenance.

The original feedback stays nested unchanged, so authority, source reference, prose, scores, rejection state, QA rule/category/severity, target identity, and artifact digest are not rewritten.

## Localization policy

F1 intentionally avoids false precision.

### Stage

- If F0 supplied `stage_hint`, F1 emits exactly that single stage with `stage_basis = "source_hint"`.
- If no stage hint exists, F1 emits the complete fixed P3 stage sequence with `stage_basis = "full_pipeline_fallback"`.

F1 does not infer a stage from human prose, owner scores, rejection state, QA category, or QA rule id. Those signals may be useful to a later planning/review step, but using them here would manufacture localization evidence that F0 did not contain.

### Region

- If F0 supplied `region_hint`, F1 emits exactly that rectangle with `region_basis = "source_hint"`.
- If no region hint exists, F1 emits the full target canvas with `region_basis = "full_canvas_fallback"`.

The fallback is deliberately conservative: lack of evidence widens the repair scope instead of guessing a smaller area.

## Determinism and reviewability

Localization is a pure provider-free transform over a validated F0 intake:

- item order is preserved,
- every feedback id appears exactly once,
- stage scopes are unique and use canonical P3 order,
- regions must fit the original target canvas,
- source hints cannot be silently narrowed, widened, or replaced,
- fallback scopes cannot be narrowed without new source evidence.

This makes the routing decision easy to inspect before F2 constructs any repair plan.

## Authority boundary

Human evidence remains human evidence. F1 never produces `all_rules_pass`, a new QA finding, or a synthetic QA failure from owner feedback.

Deterministic QA evidence also remains unchanged. F1 does not inspect a rule id and pretend it proves which authoring stage or pixels caused the failure.

## F2 boundary

F1 exposes no:

- `repair_program`,
- operation list,
- changed-pixel count,
- re-execution state,
- post-repair QA result,
- before/after evidence.

Those belong to P7-F2 and later children.

## Handoff

After P7-F1 is accepted, P7-F2 may consume these explicit scopes to construct a bounded minimal repair plan while preserving the F0/F1 provenance chain.
