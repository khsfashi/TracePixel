# P3-S7 complete staged-path evidence

This directory commits one deterministic 16x16 potion-like fixture that executes the full P3 S1-S6 path with no skipped stages.

`fixture.py` owns the frozen ArtIntent and StagePlan inputs. Running it regenerates:

- `final.rgba` — final authoritative 16x16 RGBA8 bytes;
- `01-silhouette@2x.png` through `06-outline-cleanup@2x.png` — deterministic nearest-neighbor stage snapshots;
- `manifest.json` — canonical transition evidence plus file/digest mapping (generated locally; the exact transition contract is replay-tested in CI).

CI regenerates the fixture and requires exact equality with every committed raster artifact. These files are engineering/replay evidence, not a perceptual-quality score.
