# P8-B2 Cross-Asset Consistency Contract

Status: **implemented contract/checkpoint; hand off to P8-B3 only after CI is green.**

P8-B2 freezes the boundary between deterministic shared-profile identity and visual consistency judgment. It does not add a batch drawing path, shared raster state, or a new provider call.

## Contract

`tracepixel.asset-set-consistency.v1` is derived only from the already validated `AssetSet v1`, `AssetSetRequest v1`, and member `AssetRequest v1` payloads.

The projection retains:

- canonical AssetSet and AssetSetRequest digests,
- exact declared member order and request digests,
- every member's exact digest-pinned profile references,
- one exact shared style profile across every member,
- either one exact shared palette profile across every member or no shared palette profile,
- fixed authority markers that keep visual style/palette judgment outside deterministic profile binding.

### Style binding

Every member must reference exactly one `style` profile and the full `(kind, profile_id, profile_schema, sha256)` identity must be identical across the set.

A member with no style profile, multiple style profiles, or a different style digest fails closed.

### Palette binding

A palette profile is optional because not every AssetSet has a reusable palette profile yet. When any member binds a `palette` profile, every member must bind exactly one and the full profile identity must match across the set.

Partial or conflicting palette binding fails closed. When no palette profile is bound, the contract records `palette_profile: null`; this is not a claim that the rendered palettes are visually consistent.

### Morphology and other profile context

Morphology is intentionally member-scoped. A leaf may require `leaf-form` while sibling potion icons do not. P8-B2 preserves those exact member profile refs but does not force unrelated assets to share morphology.

## Deterministic vs perceptual authority

The deterministic claim is narrow:

```text
profile_binding_policy = exact-digest-request-binding
```

It proves that every member was authored under the frozen shared style/palette/profile context declared by its request.

It does **not** prove that the output pixels look stylistically identical merely because the same style profile was referenced. Therefore both appearance policies remain:

```text
visual_style_policy   = perceptual-evidence-required
visual_palette_policy = perceptual-evidence-required
```

A later retained perceptual/human review may evaluate those visual claims. P8-B2 must not synthesize a numeric style score and promote it to deterministic QA without a separately frozen measurable rule.

## Cost and authority boundary

The builder/validator are metadata-only and perform:

- zero provider calls,
- zero pixel edits,
- no Canvas/PixelProgram mutation,
- no new raster authority,
- `O(N * P)` bounded metadata work for `N` members and at most `P` profile refs per member.

This preserves the P8-C0 result: B2 does not reintroduce batch-global provider/token overhead merely to decide consistency.

## Checkpoint

`python -m evidence.p8_b2.checkpoint` verifies that the retained reference fixture is the exact deterministic projection of the frozen P8 AssetSet requests, that visual authority cannot be tampered into a deterministic pass, and that the core-lane handoff is P8-B3.

The unit suite additionally covers:

- exact shared style binding,
- optional all-member palette binding,
- partial palette rejection,
- style-profile drift rejection,
- missing style rejection,
- closed-contract/tamper rejection.
