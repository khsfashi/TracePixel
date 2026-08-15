# Structural QA v1

`tracepixel.structural-qa.v1` is the P4-Q0 raw-fact contract over one authoritative P1 `Canvas`.

Q0 deliberately reports **facts, not policy findings**. Severity, rule identities and pass/fail policy belong to P4-Q5. Palette membership and transparent-RGB policy belong to P4-Q1.

## Visibility and alpha facts

A pixel is structurally visible when its stored alpha byte is non-zero.

Q0 records exact counts for:

- alpha `0` transparent pixels,
- alpha `1..254` translucent pixels,
- alpha `255` opaque pixels,
- total visible pixels,
- whether any translucency exists.

RGB bytes under alpha zero do not make a pixel structurally occupied. Q0 does not judge whether non-zero RGB under transparent alpha is allowed; that is a later explicit color-policy concern.

## Occupied bounds and margins

For a non-empty canvas, `occupied_bounds` is the minimum top-left, half-open rectangle containing every visible pixel:

```text
{x, y, width, height}
```

`margins` records exact empty distance from those bounds to each canvas edge:

```text
{left, top, right, bottom}
```

For an empty canvas both values are `null` because there is no occupied rectangle to anchor margins.

These are actual raster facts. Comparing them with an authored `ArtIntent.composition.occupied_bounds` requirement is intentionally not encoded as a Q0 pass/fail judgment.

## Edge contact

Q0 reports independent booleans for visible contact with the left, top, right and bottom canvas edges, plus `any` as their logical OR.

This is not a clipping/aesthetic claim. Later policy may decide that edge contact is acceptable, required or forbidden for a specific task.

## Complexity and memory

`analyze_structural(canvas)` performs one row-major `O(width * height)` pass over the package-internal read-only RGBA view.

It keeps only scalar counters, min/max bounds and edge booleans: `O(1)` auxiliary state. It does not call `Canvas.rgba_bytes()`, allocate an owned full-raster snapshot, build a coordinate set, or create a per-pixel object graph.

## Scope boundary

P4-Q0 does not add:

- palette/color-count policy,
- transparent-RGB policy,
- connectivity or isolated-pixel analysis,
- symmetry/outline diagnostics,
- tile-edge equality checks,
- typed severity/policy findings,
- perceptual style/readability/identity claims,
- provider/model, VLM, GPU, image dependency, secret or self-hosted runner.
