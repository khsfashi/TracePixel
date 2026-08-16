# P6-V2 QA / Metrics Composition

P6-V2 turns the existing P6-V0 preview bundle into one deterministic review surface that places exact image evidence beside deterministic QA and observational Agent-complexity evidence.

## Contract

`tracepixel.preview.build_qa_metrics_composition(...)` accepts one validated `PreviewBundle` and emits schema `tracepixel.qa-metrics-composition.v1`.

The materialized payload is:

```text
manifest.json
qa-metrics.svg
```

The SVG embeds the bundle's enlarged preview PNG byte-for-byte. It reads only the PNG IHDR for dimensions and places the image at its natural dimensions. It does not decode, resample, or re-encode raster pixels.

The composition consumes the already-bundled evidence rather than rerunning QA or an Agent provider:

- `evidence/qa-findings.json` remains the deterministic QA source,
- `evidence/agent-complexity.json`, when present, remains observational evidence,
- image bytes remain derived from the authoritative raster through P6-V0,
- no perceptual/VLM score or human judgment is introduced.

## Manifest

The manifest records:

- exact source preview path, byte size, SHA-256 and dimensions,
- exact deterministic QA evidence path/digest plus the source findings,
- exact Agent-complexity evidence path/digest plus telemetry when available,
- deterministic SVG dimensions, byte size and SHA-256,
- explicit authority labels for raster, deterministic QA, complexity, perceptual evidence and human judgment.

`status: pass` means the source deterministic finding list is empty. It is only a presentation summary of the source evidence; the composition itself is not a new QA authority.

## Determinism and bounds

- identical P6-V0 bundle bytes produce identical SVG and manifest bytes,
- P4 already bounds the deterministic finding set,
- P5-A3 fixes the closed telemetry field set,
- the composition performs no provider/network call,
- the output writer refuses a non-empty directory so stale review files cannot leak into a new composition.

The only image-sized work is base64 serialization of the existing preview PNG into the SVG. There is no second raster buffer or pixel decode/re-encode pass.

## Authority boundary

P6-V2 is presentation state only.

- authoritative raster truth is unchanged,
- deterministic QA remains source evidence from P4/P6-V0,
- Agent complexity is observational and never correctness truth,
- perceptual/VLM evidence is `not-included`, so unresolved owner gate G4 is not crossed,
- human judgment is `not-included` and is not serialized as deterministic evidence.

## Portable checkpoint

P6-V2 reuses the frozen P5-A5 real-provider reference through the provider-free P6-V0 replay:

```bash
python -m evidence.p6_v2.checkpoint
```

The checkpoint rebuilds the P6-V0 bundle without a provider call, creates the composition twice, requires byte-identical output, verifies the exact preview digest, deterministic QA pass state, frozen Agent-complexity values and authority separation, then materializes the files in a temporary directory.

To keep a generated copy:

```bash
python -m evidence.p6_v2.checkpoint --output out/p6-v2-reference
```

No provider call, network access, secret, GPU, VLM, or self-hosted runner is required.

## Scope boundary

P6-V2 stops at image + evidence composition. Static HTML is P6-V3; GitHub artifact publishing is P6-V4; the proven mobile review flow is P6-V5; optional home-PC preview execution remains behind G6 at P6-V6.
