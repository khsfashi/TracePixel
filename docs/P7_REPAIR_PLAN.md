# P7-F2 Minimal Repair Plan

P7-F2 consumes validated `tracepixel.feedback-localization.v1` evidence and turns explicit repair proposals into a bounded, canonical `tracepixel.repair-plan.v1`. It does **not** execute the repair, compare the repaired raster to the original, rerun QA, or produce before/after evidence.

## Contract

`tracepixel.repair-plan.v1` contains:

- the exact validated F1 `localization`,
- one ordered repair/defer decision per localization item,
- an explicit target stage for active repairs,
- a canonical bounded PixelProgram for active repairs,
- the exact planned edit bounding box,
- planned operation and pixel-edit counts,
- a bounded reason when a finding is deliberately deferred.

The original F0 intake remains nested inside F1, so target identity and feedback authority/provenance are retained unchanged.

## Proposal boundary

F2 never converts owner prose, scores, rejection state, QA rule ids, or QA categories into pixel edits.

A caller must explicitly provide either:

- a target stage plus a PixelProgram proposal, or
- no program plus a non-blank defer reason.

This keeps human evidence human and avoids pretending that a deterministic QA finding contains a repair that it never supplied.

## Bounded stage and region

An active repair must select a `target_stage` that is already present in the corresponding F1 `affected_stages`.

Every proposed pixel coordinate must be inside the corresponding F1 `affected_region`. F2 may therefore choose a smaller **planned edit footprint** inside the conservative F1 scope, but it cannot write outside the scope.

The full PixelProgram canvas must still equal the original F0 target canvas. The localized region bounds writes; it does not create a detached sub-canvas with different coordinate semantics.

## Minimal canonical form

PixelProgram v1 currently contains only ordered exact `set_pixels` operations. That allows F2 to minimize a proposal without executing the raster:

1. validate the proposal as PixelProgram v1,
2. flatten all `set_pixels` writes,
3. retain the last proposed write for each coordinate,
4. sort unique coordinates by stable `(y, x)` order,
5. emit exactly one `set_pixels` operation.

This is semantic-preserving for the current PixelProgram v1 operation vocabulary and removes redundant planned writes. F2 does **not** know whether a proposed RGBA value already equals the source raster, so `planned_pixel_edit_count` is a proposal-cost metric, not an observed changed-pixel count.

`planned_region` is the exact bounding box of the canonical unique pixel coordinates. `planned_operation_count` is therefore `1` for an active repair and `0` for a deferred item.

## Defer path

A localization item may be retained as `defer` when no explicit bounded repair is available yet. Deferred items have:

- `target_stage = null`,
- `planned_region = null`,
- `repair_program = null`,
- zero planned operation/pixel counts,
- a required bounded `defer_reason`.

This is preferable to manufacturing a repair from subjective feedback or insufficient evidence.

## F3 boundary

F2 exposes no:

- executed repair state,
- observed changed-pixel count,
- post-repair raster digest,
- QA result or `all_rules_pass`,
- unaffected-region stability result,
- before/after artifact evidence.

Those require a source raster and execution and belong to P7-F3 and P7-F4.

## Handoff

After P7-F2 is accepted, P7-F3 may execute only the canonical active repair programs, measure actual mutation cost/stability, and rerun deterministic QA while preserving the F0 -> F1 -> F2 provenance chain.
