# Shape / Outline QA v1

`tracepixel.shape-outline-qa.v1` is the P4-Q3 exact shape/outline fact contract over one authoritative P1 `Canvas`.

Q3 reports objective visibility geometry only. It does not turn outline smoothness, jaggedness, recognizability, style, or color-stroke appearance into deterministic truth.

## Visibility

Q3 uses the same structural visibility rule as P4-Q0 through Q2:

- `alpha == 0` is not visible,
- `alpha != 0` is visible, including translucent pixels.

RGB bytes hidden below alpha zero do not participate in shape geometry.

## Explicit required symmetry

Symmetry is evaluated only when the caller passes `required_symmetry`:

```text
vertical | horizontal | both
```

If the argument is omitted, `symmetry` is `null` and an asymmetric raster is not classified.

This matches the P3 `ArtIntent` authority split: a `hint` is authored guidance, while an exact Q3 check is appropriate only when the task explicitly requires an axis.

Version 1 defines shape symmetry over the binary visibility mask and the full canvas center axis:

- vertical mirror of `(x, y)` is `(width - 1 - x, y)`,
- horizontal mirror of `(x, y)` is `(x, height - 1 - y)`,
- odd-width/odd-height center positions mirror to themselves and are not counted as pairs,
- RGBA colors are not compared as part of shape symmetry.

For each requested axis Q3 records:

```text
{matches, mismatched_pairs}
```

`mismatched_pairs` counts each unique mirrored position pair once when exactly one side is visible.

Color/palette symmetry is deliberately not inferred. If a future task needs exact mirrored color identity, that must be an explicit separate contract rather than silently changing shape symmetry.

## Finite adjacency and outline diagnostics

For every visible pixel Q3 records objective 4-neighbor geometry:

- `boundary_pixels`: visible pixels with at least one side touching canvas exterior or an invisible pixel,
- `interior_pixels`: visible pixels whose four edge-neighbors are all visible,
- `visible_adjacencies.horizontal`: unique left/right visible neighbor pairs,
- `visible_adjacencies.vertical`: unique top/bottom visible neighbor pairs,
- `exposed_edges.top/right/bottom/left`: visible pixel sides touching exterior/invisible space,
- `exposed_edges.total`: exact pixel-edge perimeter length.

Adjacency pairs are counted once by checking only right and down neighbors. Therefore the exact identity

```text
exposed_edges.total
  = 4 * visible_pixels
  - 2 * visible_adjacencies.total
```

holds for every raster.

These are finite structural facts. Q3 does not label a large perimeter, many boundary pixels, stair steps, diagonal contacts, or any other outline pattern as aesthetically bad.

## Deterministic scan and memory

`analyze_shape_outline(canvas, required_symmetry=...)` performs one row-major raster scan.

The implementation:

- borrows the package-internal read-only RGBA view,
- never calls `Canvas.rgba_bytes()`,
- allocates no second raster,
- retains only scalar counters and a small fixed result object,
- does not construct coordinate sets, masks, contours, or per-pixel object graphs.

Let `P = width * height`. Runtime is `O(P)` and auxiliary analysis state is `O(1)`.

## Scope boundary

P4-Q3 does not add:

- automatic symmetry policy from hints,
- exact mirrored color/palette checks,
- contour tracing or coordinate-list evidence,
- universal jaggedness/smoothness thresholds,
- style, readability, identity, or aesthetic quality judgments,
- tile-edge equality,
- typed severity/category/rule findings,
- automatic cleanup,
- provider/model, VLM, GPU, image dependency, secret, or self-hosted runner.

The next child is P4-Q4 tile-edge QA, but the machine-readable core lane advances only after Q3 portable CI is green.
