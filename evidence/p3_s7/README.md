# P3-S7 complete staged-path evidence

This directory commits one deterministic 16x16 potion-like fixture that executes the full P3 S1-S6 path with no skipped stages.

Committed evidence:

- `final.rgba` — final authoritative 16x16 RGBA8 bytes;
- `stage-preview.svg` — human-inspectable contact sheet showing the six raster states in stage order;
- `fixture.py` — frozen ArtIntent and StagePlan inputs plus deterministic evidence regeneration.

Running `fixture.py` regenerates `final.rgba`, six deterministic `@2x.png` nearest-neighbor previews, and `manifest.json` locally. CI freezes the final RGBA bytes and all six generated PNG SHA-256 values, while the SVG is supplementary visual evidence that remains safe to store through text-only GitHub tooling.

The SVG is not raster authority and is not used for replay. Canonical transition evidence always hashes the authoritative RGBA state and the deterministic PNG export produced by TracePixel.
