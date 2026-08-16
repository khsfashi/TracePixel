# P7-F4 Before/After Repair Evidence

P7-F4 turns one bounded P7-F3 repair execution into reviewable byte-addressed evidence. It captures deterministic PNG evidence immediately before execution, runs the existing F3 executor exactly once, captures deterministic PNG evidence immediately after execution, retains the exact F3 QA JSON, and emits one dependency-free static HTML comparison page.

It does not reinterpret feedback, author new repair pixels, rerun frozen B0 evidence, record human approval, or invoke a VLM/perceptual judge.

## Contract

`tracepixel.repair-evidence.v1` retains the complete validated `tracepixel.repair-execution.v1` object and records:

- exact native PNG before repair,
- nearest-neighbor enlarged PNG before repair,
- exact native PNG after repair,
- nearest-neighbor enlarged PNG after repair,
- canonical final deterministic QA JSON from F3,
- one self-contained static HTML before/after gallery,
- byte size and SHA-256 for every materialized artifact,
- authoritative RGBA SHA-256 linkage for every PNG,
- an explicit authority boundary that keeps human review unrecorded and perceptual judgment absent.

The provenance chain is therefore F0 intake -> F1 localization -> F2 repair plan -> F3 execution/re-QA -> F4 visual evidence.

## Raster identity

F4 exports the pre-execution native and enlarged PNGs before calling F3. It then calls `execute_repair_plan(...)` exactly once on the caller-owned `Canvas` and exports the post-execution native and enlarged PNGs.

The PNG exporter already records the authoritative source RGBA digest. F4 requires:

- both `before` PNGs to match F3 `source_rgba_sha256`,
- both `after` PNGs to match F3 `result_rgba_sha256`.

A bundle is rejected if either side is linked to the wrong raster identity. The manifest separately hashes the encoded PNG bytes, so the authoritative raster identity and the exact review-file identity remain distinct.

## Memory boundary

F4 does not retain a second authoritative raw raster. The caller-owned `Canvas` remains the only mutable authoritative raster.

Before execution, F4 retains only the encoded native/preview PNG bytes required as evidence. F3 then uses its existing single transient source RGBA snapshot for exact mutation accounting. After execution, F4 exports encoded result PNGs directly from the final Canvas read-only view.

This deliberately avoids a permanent full-size before/after raw-raster pair while still producing reviewable evidence.

## Deterministic QA evidence

`evidence/qa-findings.json` is the canonical JSON encoding of the exact F3 `qa` object. F4 does not synthesize `all_rules_pass`, combine owner ratings with QA, or infer aesthetic completion from an empty findings list.

The HTML page shows the deterministic QA finding count and exact QA JSON only as deterministic evidence.

## Static HTML gallery

`index.html` embeds the enlarged before/after PNGs as `data:` URIs and requires no server after materialization.

The page intentionally has:

- no JavaScript,
- no external network resource,
- a restrictive Content Security Policy,
- responsive single-column fallback on narrow screens,
- `overflow-wrap`/`word-break` protection for long task or evidence text,
- pixelated nearest-neighbor rendering,
- an explicit notice that deterministic QA and visual evidence are not human/perceptual acceptance.

The HTML is an inspection surface only. PNG and JSON files remain separately hashed evidence artifacts.

## Materialization

`write_repair_evidence_bundle(...)` writes the complete bundle and refuses to mix it into a non-empty output directory. This prevents stale files from being mistaken for the current evidence set.

The materialized paths are:

```text
manifest.json
before/native.png
before/preview-<scale>x.png
after/native.png
after/preview-<scale>x.png
evidence/qa-findings.json
index.html
```

## F5 boundary

F4 records no:

- human approval/rejection update,
- new human score,
- perceptual/VLM score or verdict,
- automatic authoring-complete decision.

P7-F5 owns the bounded human-feedback contract. F4 only gives that later step exact source/result/QA artifacts to review.

## Handoff

After P7-F4 is accepted, advance only to P7-F5. Frozen B0 evidence remains immutable, and no unresolved owner gate is crossed by this provider-free visual-evidence step.
