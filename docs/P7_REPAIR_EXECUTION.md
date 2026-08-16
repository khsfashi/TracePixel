# P7-F3 Repair Execution and Re-QA

P7-F3 consumes a validated `tracepixel.repair-plan.v1`, applies only its canonical active repair programs to the caller-owned authoritative `Canvas`, measures actual mutation cost, and reruns deterministic QA. It does not generate a repair, reinterpret human feedback, emit preview artifacts, or decide human/perceptual completion.

## Contract

`tracepixel.repair-execution.v1` retains the exact validated F2 `plan` and records:

- source and post-repair authoritative RGBA SHA-256 digests,
- one ordered execution record per F2 repair/defer item,
- applied operation and pixel-edit counts,
- per-repair observed changed-pixel counts,
- the final source-to-result changed-pixel count,
- measured stability outside the exact F2 planned write coordinates,
- final deterministic `tracepixel.qa-findings.v1` evidence.

The nested provenance remains F0 intake -> F1 localization -> F2 repair plan -> F3 execution.

## Execution boundary

F3 executes the F2 plan; it does not author it.

- `repair` items are applied in F2 order using their already-canonical PixelPrograms.
- `defer` items remain deferred and consume zero operation, pixel-edit, and changed-pixel cost.
- The target `Canvas` dimensions must exactly equal the original F0 target canvas.
- F3 never infers edits from owner prose, perceptual scores, deterministic rule ids, or QA categories.

The caller-owned Canvas is mutated in place. This matches the existing deterministic PixelProgram executor and avoids constructing a second authoritative raster.

## Mutation accounting

F2's `planned_pixel_edit_count` counts unique proposed write coordinates. It cannot know whether a proposed RGBA value already equals the source value.

F3 therefore separates three costs:

1. `applied_pixel_edit_count`: exact canonical writes executed,
2. per-item `observed_changed_pixel_count`: touched coordinates whose value changed during that item,
3. top-level `observed_changed_pixel_count`: pixels whose final RGBA differs from the original source raster.

The top-level count is intentionally source-to-result rather than a sum of per-item counts. If two ordered repairs touch the same coordinate, or a later repair restores the source value, summing per-item changes would overstate final mutation.

## Memory and stability

F3 takes exactly one owned source `rgba_bytes()` snapshot because an exact source digest and final source-to-result comparison require source bytes. It does not allocate a second final snapshot: final hashing and comparison borrow the Canvas read-only view.

Per-repair accounting captures only the unique touched positions. The final stability scan verifies that any source-to-result change lies inside the union of exact active F2 PixelProgram coordinates. `unaffected_region_stable` therefore means **all pixels outside planned write coordinates are byte-identical to the F3 source snapshot**.

This is stricter than checking only the F2 bounding boxes and avoids treating untouched holes inside a bounding box as intentionally mutable.

## Re-QA authority

The caller supplies a provider-free `RepairQaEvaluator` with the same structural shape as the existing Agent-loop QA boundary: `evaluate(Canvas) -> QaFindingsV1`.

F3 validates that returned QA evidence is the closed deterministic Q5 findings shape:

- supported rule id,
- rule-matching category,
- `info` / `warning` / `error` severity,
- no duplicate rule,
- no human or perceptual fields.

F3 does **not** expose `all_rules_pass` or reinterpret an empty findings list as authoring completion. Empty deterministic findings only mean that the evaluator's selected deterministic policy has no remaining findings. Human/perceptual acceptance stays separate.

## F4 boundary

F3 emits no:

- native or enlarged PNG preview,
- before/after contact sheet,
- before/after HTML/gallery evidence,
- human approval/rejection update,
- VLM/perceptual judgment.

Those belong to P7-F4 before/after evidence and P7-F5 human-feedback contract.

## Handoff

After P7-F3 is accepted, P7-F4 may render reviewable before/after visual evidence from the retained source/result identity and deterministic QA evidence without mutating frozen B0 evidence or crossing a human/VLM owner gate.
