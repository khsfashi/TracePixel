# Tile Edge QA v1

`tracepixel.tile-edge-qa.v1` is the P4-Q4 exact tile-edge fact contract over one authoritative P1 `Canvas`.

Q4 answers only byte-exact tiling questions. It does not claim that a matching edge is visually good, that a mismatching edge is always a defect, or that a tile is perceptually seamless under filtering, blending, animation, lighting, or neighboring context.

## Exact edge equality

Q4 always compares opposite authoritative raster boundaries:

- `left_right`: `(0, y)` versus `(width - 1, y)` for every row,
- `top_bottom`: `(x, 0)` versus `(x, height - 1)` for every column.

Each result records:

```text
{compared_positions, mismatched_positions, matches}
```

Equality is exact RGBA8 byte equality. This deliberately includes RGB bytes stored under alpha zero because P1 defines dimensions plus exact authoritative RGBA bytes as replay truth.

If a workflow wants perceptual equivalence that ignores hidden transparent RGB, filtering behavior, or atlas padding, that is a different explicit contract and must not silently change Q4 v1 equality.

A one-pixel-wide tile has the same left and right position, and a one-pixel-high tile has the same top and bottom position. Those comparisons therefore match with zero mismatches.

## Corner facts

Q4 always records:

```text
corners = {
  all_equal,
  distinct_rgba_colors
}
```

The four logical corner positions are top-left, top-right, bottom-left, and bottom-right. Degenerate dimensions may make multiple logical corners refer to the same pixel; the distinct-color count is still computed over those four logical positions.

## Explicit tile contracts

Raw equality facts are always present. A pass/fail-style `contract` object is emitted only when the caller explicitly requests one or more requirements:

```text
required_edges = left_right | top_bottom | both | None
require_equal_corners = bool
```

When neither requirement is supplied, `contract` is `null`.

When requested, Q4 reports:

```text
{
  required_edges,
  require_equal_corners,
  satisfied
}
```

`satisfied` is the conjunction of only the explicitly requested edge/corner equalities. It carries no severity, category, repair action, or universal defect meaning. Typed policy findings remain P4-Q5 scope.

## Deterministic boundary scan and memory

`analyze_tile_edges(canvas, ...)` reads only boundary pixels.

The implementation:

- borrows the package-internal read-only RGBA view,
- never calls `Canvas.rgba_bytes()`,
- compares channels directly instead of materializing row/column snapshots,
- keeps only scalar counters plus a set of at most four packed corner colors,
- allocates no second raster, edge image, coordinate graph, or per-pixel object collection.

Let `W = width` and `H = height`. Runtime is `O(W + H)` and auxiliary analysis state is `O(1)`.

## Scope boundary

P4-Q4 does not add:

- tolerance-based or perceptual edge similarity,
- filtered/blurred/antialiased sampling semantics,
- atlas padding or neighboring-tile composition,
- automatic wrap-mode inference,
- tile repair or edge synthesis,
- typed severity/category/rule findings,
- style, readability, identity, or aesthetic quality judgments,
- provider/model, VLM, GPU, image dependency, secret, or self-hosted runner.

The next child is P4-Q5 typed findings + policy, but the machine-readable core lane advances only after Q4 portable CI is green.
