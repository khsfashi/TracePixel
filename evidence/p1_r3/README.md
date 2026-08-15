# P1-R3 Replay Fixture Evidence

This directory freezes the first human-visible deterministic TracePixel raster fixture.

The fixture is a **16×16 potion**. It deliberately uses only the existing P1 `Canvas.set_pixels()` mutation surface and P1-R2 export functions; the row/palette notation is fixture-local evidence and is **not** a public Pixel IR or drawing vocabulary.

## Committed evidence

- `potion.rgba` — exact 1024-byte authoritative row-major RGBA8 replay truth.
- `potion.png` — deterministic native 16×16 encoder-v1 PNG.
- `potion@4x.png` — deterministic 64×64 nearest-neighbor preview.
- `manifest.json` — stable fixture/program/output metadata and SHA-256 evidence.
- `potion.py` — deterministic fixture program and evidence regenerator.

![4x nearest-neighbor potion preview](potion@4x.png)

## Regenerate

From the repository root after installing TracePixel editable:

```bash
python -m evidence.p1_r3.potion
python -m unittest tests.test_p1_r3_replay_fixture -v
```

The test requires regenerated authoritative RGBA, native PNG, preview PNG and structural metadata to match the committed evidence exactly.
