# P6-V3 Static HTML Gallery

P6-V3 packages the existing P6-V0 preview bundle, P6-V1 stage contact sheet and P6-V2 QA/metrics composition into one deterministic, self-contained review page suitable for phone browsers.

## Contract

`tracepixel.preview.build_static_html_gallery(...)` accepts:

- one `PreviewBundle`,
- one `StageContactSheet`,
- one `QaMetricsComposition`.

It emits schema `tracepixel.static-html-gallery.v1` and the materialized payload:

```text
manifest.json
index.html
```

The HTML is deliberately dependency-free. It uses no JavaScript, remote stylesheet, web font, external image URL or server API. All review imagery is embedded as data URIs and a restrictive Content Security Policy prevents network-backed page dependencies.

## Review surface

The page exposes, in one mobile-friendly flow:

- final enlarged nearest-neighbor preview,
- deterministic QA status and Agent-complexity composition,
- authored-stage contact sheet,
- task / ArtIntent JSON,
- explicit authority boundaries.

The page contains responsive CSS only. Browser layout may scale the already-produced review images for the viewport, but it never mutates source raster bytes or creates a second raster authority.

## Source verification

Before emitting HTML, P6-V3 verifies:

- the in-memory P6-V0 manifest matches the canonical `manifest.json` bundled with it,
- preview, intent and deterministic-QA bundle files match their recorded sizes and SHA-256 digests,
- P6-V1 and P6-V2 SVG bytes match their own manifests,
- P6-V2 references the same preview, deterministic QA and optional complexity evidence as the supplied P6-V0 bundle,
- when a bundle declares stage-image artifacts, every P6-V1 contact-sheet frame matches the corresponding path and digest.

The frozen P5-A5 reference bundle contains no stage artifacts because that real-provider smoke proposed one final PixelProgram rather than running the P3 staged authoring path. The P6-V3 reference gallery therefore records the committed P6-V1 sheet with `linkage: separate-reference` instead of pretending those stage frames are provenance for the P5-A5 final image. A future bundle that actually contains stage-image artifacts is recorded as `bundle-stage-artifacts` only after exact path/digest linkage succeeds.

## Determinism and cost

Identical source evidence produces identical UTF-8 HTML and manifest bytes. No timestamp, random identifier, provider response or environment-specific path enters the output.

P6-V3 performs no image decode/re-encode pass and no per-pixel work. Its primary extra memory/work is base64 serialization of already-generated PNG/SVG evidence plus construction of one HTML byte string. This is an offline review artifact, not a frame-loop/runtime surface.

The writer refuses a non-empty output directory so stale files cannot be mixed into a new gallery.

## Authority boundary

P6-V3 remains presentation-only:

- authoritative raster truth is unchanged,
- deterministic QA remains source evidence,
- P6-V1/P6-V2 compositions remain presentation surfaces,
- Agent complexity remains observational,
- perceptual/VLM evidence is not included, so unresolved owner gate G4 is not crossed,
- human aesthetic judgment is not encoded as deterministic truth.

P6-V3 does not publish artifacts, run a server, call a provider, use a GPU or enable a self-hosted runner.

## Portable checkpoint

Run:

```bash
python -m evidence.p6_v3.checkpoint
```

The checkpoint rebuilds the frozen/provider-free P6-V0/V1/V2 reference evidence, creates the gallery twice, requires deterministic equality, verifies source digests and authority labels, checks the page contains mobile viewport/CSP metadata and no script/network resources, then materializes the gallery in a temporary directory.

To keep a generated copy:

```bash
python -m evidence.p6_v3.checkpoint --output out/p6-v3-reference
```

No provider call, network access, secret, GPU, VLM or self-hosted runner is required.

## Scope boundary

P6-V3 stops at static local HTML generation. GitHub artifact publishing is P6-V4; proving the owner review path on mobile is P6-V5; optional owner Windows preview execution remains behind G6 at P6-V6.
