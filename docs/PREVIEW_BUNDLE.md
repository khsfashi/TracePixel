# P6-V0 Preview Bundle

P6-V0 packages already-authoritative TracePixel output into a deterministic, portable review payload. It does not create a second raster authority and it does not require a live model/provider call.

## Contract

`tracepixel.preview.build_preview_bundle(...)` produces schema `tracepixel.preview-bundle.v1` with this baseline layout:

```text
manifest.json
image/
  native.png
  preview-<scale>x.png
evidence/
  intent.json
  qa-findings.json
  agent-complexity.json      # only when available
stages/
  <stage>/<artifact>         # zero or more available stage images/evidence
```

The manifest records exact path, media type, byte length and SHA-256 for every payload file. Native/preview records also carry the existing deterministic PNG export metadata, including the authoritative RGBA digest. There is no timestamp or provider identifier in the V0 manifest, so identical inputs produce identical bundle bytes.

`write_preview_bundle(...)` refuses to write into a non-empty directory. This prevents a new bundle from silently inheriting stale files from an older review run.

## Authority boundaries

- The `Canvas` authoritative RGBA state remains raster truth.
- `image/native.png` and the enlarged preview are deterministic derivatives of that same RGBA state.
- `evidence/qa-findings.json` contains deterministic Q5 findings only.
- `evidence/intent.json` is authoring input/intent, not a correctness verdict.
- `evidence/agent-complexity.json` is observational complexity evidence when available; it is not raster or QA authority.
- Optional stage attachments are preserved byte-for-byte and hashed in fixed P3 stage order. They do not replace stage replay evidence or canonical pixels.
- Perceptual/VLM judgment is intentionally absent from V0. G4 remains unresolved.

## Portable reference checkpoint

The committed P5-A5 real-provider result is reused without calling the provider again:

```bash
python -m evidence.p6_v0.checkpoint
```

The checkpoint replays the frozen provider PixelProgram, re-runs deterministic QA, validates the existing Agent-complexity telemetry, rebuilds a V0 bundle, materializes it to a temporary directory, and requires the native/8x preview PNG bytes to exactly match the committed P5-A5 evidence.

To keep a generated copy for inspection, point the checkpoint at an empty/non-existent directory:

```bash
python -m evidence.p6_v0.checkpoint --output out/p6-v0-reference
```

No Codex install, login, API key, network provider request, GPU, VLM, or self-hosted runner is required.

## Scope boundary

V0 only defines the smallest complete review payload. Contact-sheet composition is P6-V1, QA/metrics visual composition is P6-V2, static HTML is P6-V3, artifact publication is P6-V4, the proven mobile review flow is P6-V5, and any optional home-PC preview runner remains behind G6 at P6-V6.
