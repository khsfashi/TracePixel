# Connectivity QA v1

`tracepixel.connectivity-qa.v1` is the P4-Q2 exact connectivity/isolation fact contract over one authoritative P1 `Canvas`.

Q2 reports topology facts only. It does not classify disconnected shapes or isolated pixels as defects; severity, rule identity and pass/fail policy remain P4-Q5 scope.

## Visibility

Connectivity uses the same structural visibility rule as P4-Q0 and P4-Q1:

- `alpha == 0` is not visible,
- `alpha != 0` is visible, including translucent pixels.

RGB bytes hidden below alpha zero do not participate in topology.

## Fixed 4-neighbor connectivity

Version 1 uses edge adjacency only:

```text
    up
left P right
   down
```

Two visible pixels belong to the same connected component when a path exists through visible up/down/left/right neighbors.

Diagonal corner contact alone does **not** connect components. Q2 records the connectivity identity as `4` so callers do not have to infer the adjacency convention.

The v1 contract deliberately does not offer an implicit 8-neighbor alternative. A different adjacency definition would change exact topology identity and must be explicit in a future version rather than silently changing existing evidence.

## Connected-component facts

Q2 records:

- `visible_pixels`: exact number of structurally visible pixels,
- `components.count`: exact number of 4-neighbor visible components,
- `components.largest_pixels`: exact pixel cardinality of the largest component.

An empty raster has zero visible pixels, zero components and a largest-component size of zero.

Component coordinates, masks and arbitrary per-component object graphs are intentionally not retained by this fact surface. Later consumers that need targeted locality should use an explicit bounded contract rather than making Q2 return raster-sized coordinate collections by default.

## Isolated-pixel facts

A visible pixel is isolated exactly when its 4-neighbor connected component contains one pixel.

Q2 records:

```text
{count, has_isolated_pixels}
```

This is an objective topology fact, not a universal cleanup rule. Single-pixel components can be intentional in pixel art; P4-Q5 may only turn the fact into a finding when an explicit policy requests it.

## Deterministic traversal

`analyze_connectivity(canvas)` discovers components in row-major seed order and uses an iterative flood traversal.

The implementation:

- borrows the package-internal read-only RGBA view,
- never calls `Canvas.rgba_bytes()`,
- uses one bit per raster position for visited state,
- stores pending pixel indices in a packed unsigned-integer array,
- marks a visible neighbor visited before pushing it,
- uses no recursion,
- creates no per-pixel tuples, coordinate objects or Python set of visited pixels.

Traversal order is deterministic, although the public Q2 result intentionally exposes only order-independent exact facts.

## Complexity and memory

Let `P = width * height`.

The row-major discovery scan is `O(P)`. During flood traversal every visible pixel is popped exactly once and has at most four neighbors examined, so the complete analysis remains `O(P)`.

Auxiliary memory is `O(P)` worst-case but compact and bounded by the raster contract: a one-bit-per-position visited bitmap plus a packed pending-index array. The analyzer does not allocate a second RGBA raster or retain an object per canvas pixel.

## Scope boundary

P4-Q2 does not add:

- 8-neighbor or perceptually inferred connectivity,
- connectedness pass/fail policy,
- isolated-pixel severity or automatic cleanup,
- symmetry or outline diagnostics,
- tile-edge equality,
- typed severity/category/rule findings,
- aesthetic jaggedness/readability/recognizability judgments,
- provider/model, VLM, GPU, image dependency, secret or self-hosted runner.

The next child is P4-Q3 shape/outline QA, but the machine-readable core lane advances only after Q2 portable CI is green.
