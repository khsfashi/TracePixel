# P8-B5 Batch Preview + Mobile Review

Status: **review-surface implementation. P8 remains on B5 until retained outputs receive owner mobile review; do not advance to P8-B6 from the CI fixture alone.**

P8-B5 adds one presentation/evidence layer over the existing per-member single-asset authority. It does not add a batch renderer, shared Canvas, new PixelProgram path, provider-side batch planner, or a second raster truth.

## Package contract

`tracepixel.preview.batch_review` builds `tracepixel.batch-review-package.v1` from an ordered list of existing member PNG outputs.

Each member retains:

- exact `member_id`,
- exact asset class and native canvas dimensions,
- original native PNG bytes embedded by data URI,
- exact PNG SHA-256,
- a retained source reference,
- explicit `source_kind`: `retained-output` or `presentation-fixture`.

The HTML does not generate enlarged PNGs. One original PNG data URI is emitted once per member per language page and the native/inspection/tile views reuse that CSS image with nearest-neighbor rendering. This keeps package construction bounded and avoids creating redundant enlarged raster copies.

## Mobile and security boundary

The package emits two static pages:

- `index.html` — English
- `index.ko.html` — Korean

Both pages require the mobile viewport contract and remain:

- script-free,
- network-free,
- server-free,
- external-asset-free,
- provider-free,
- GPU-free,
- self-hosted-runner-free.

The CSP permits only embedded `data:` images and inline presentation CSS. Static companion-page links handle language switching.

## Per-member evidence is never erased

The aggregate page must show every member independently before any tile composition. Each card exposes the member identity, class, native dimensions, source reference and PNG digest beside the native-1x and nearest-neighbor inspection views.

A tile patch is an additional view over the same retained member PNG bytes. It is not a replacement for per-member evidence and is not a new atlas/raster authority.

## Deterministic vs perceptual authority

P8-B5 may deterministically verify:

- member identity/order,
- asset class,
- native dimensions from PNG IHDR,
- exact PNG SHA-256,
- source reference,
- declared tile placement,
- package/page digests,
- absence of scripts/network dependencies,
- static bilingual/mobile review structure.

P8-B5 must **not** deterministically claim:

- recognizability,
- native-1x readability,
- cross-asset style coherence,
- visual palette coherence,
- tile pixel seamlessness,
- tile repetition quality,
- mobile visual scanability.

Those remain perceptual/human evidence. Human judgment is retained separately and is never promoted to deterministic QA truth.

## Fixture fail-closed rule

Portable CI uses a tiny deterministic presentation fixture generated through the existing P1 `Canvas` + native PNG exporter. The fixture exists only to exercise the package, mobile layout, member retention, tile composition and security boundary.

If any member uses `source_kind=presentation-fixture`, the package review scope fails closed to `presentation-fixture`. Such a package cannot support a production-quality claim. A production review package must contain only `retained-output` members.

This distinction prevents attractive fixture pixels from being mistaken for evidence that the P8 authoring path produced the same quality.

## Review dimensions before P8-B6

A retained-output owner review should inspect at minimum:

1. cross-asset style coherence,
2. palette coherence,
3. tile pixel seam quality,
4. native-1x readability,
5. mobile scanability.

P8-B6 stays blocked until the retained-output package has been reviewed on a phone and the review is recorded as perceptual owner evidence.

## Checkpoint

Portable verification:

```bash
python -m evidence.p8_b5.checkpoint
```

Materialize the safe bilingual fixture package:

```bash
python -m evidence.p8_b5.checkpoint --output out/p8-b5-review
```

The GitHub-hosted `P8 batch review artifact` workflow publishes the same package as an artifact for phone layout inspection after merge. It performs no paid/provider call and does not imply production-quality approval.
