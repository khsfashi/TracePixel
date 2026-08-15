# P4-Q5 seeded deterministic QA checkpoint

This directory freezes the early P4 engineering checkpoint required by the roadmap.

The checkpoint contains two 5x5 authoritative raster fixtures built only with the existing `Canvas` mutation API:

- `clean`: one centered opaque 3-pixel vertical component. All ten selected policy rules pass and Q5 emits zero findings.
- `seeded_defects`: deliberately injects exact structural defects so nine selected rules fail in a stable order.

Seeded defects are:

1. one opaque red pixel at `(0, 0)` to create visible edge contact and an isolated component,
2. one connected blue body at `(2, 1)` / `(2, 2)`,
3. one connected translucent green pixel at `(1, 2)` to create translucency, palette non-membership, color-budget overflow, and vertical-symmetry mismatch,
4. one hidden non-zero RGB value `(9, 9, 9, 0)` at `(4, 4)` to violate the explicit transparent-RGB policy and exact tile-edge/corner contract.

The configured Q1 palette intentionally contains only the opaque red and blue colors and sets a two-color maximum. Q3 explicitly requires vertical symmetry. Q4 explicitly requires both opposite-edge equalities plus equal corners. Q5 therefore classifies only already-requested deterministic checks; it does not invent these requirements.

## Files

- `checkpoint.py` regenerates canonical structural evidence from Q0-Q5.
- `structural.json` is the committed canonical result compared by portable tests.
- `preview.svg` is a human-readable explanatory preview placed beside the finding summary. It is not raster authority.

Run from the repository root:

```bash
python evidence/p4_q5/checkpoint.py
python -m unittest tests.test_p4_q5_evidence -v
```

The checkpoint requires only the standard library and TracePixel itself. No provider, VLM, GPU, external image package, secret, network access, or self-hosted runner participates in the result.

## Frozen expected result

`clean` emits `0` findings.

`seeded_defects` emits `9` findings, in policy order:

```text
structural.no_translucency       warning
structural.no_edge_contact       warning
color.palette_membership         error
color.maximum_colors             error
color.transparent_rgb_policy     error
connectivity.single_component    error
connectivity.no_isolated_pixels  warning
shape.required_symmetry          error
tile.contract                    error
```

This fixture measures deterministic defect coverage only. It makes no claim about beauty, readability, identity, or style quality.
