# Color QA v1

`tracepixel.color-qa.v1` is the P4-Q1 palette/color analysis contract over one authoritative P1 `Canvas`.

Q1 keeps **raw exact color facts** separate from **explicitly requested checks**. It does not emit severity/category/rule findings; typed findings belong to P4-Q5.

## Visible color count

A color counts toward the pixel-art palette only when the stored alpha byte is non-zero.

`colors.visible_rgba_colors` is the exact number of distinct visible RGBA8 values. Alpha is part of the color identity, so `(r,g,b,128)` and `(r,g,b,255)` are distinct.

RGB bytes under alpha zero do not increase the visible color count. They are reported independently by the transparent-RGB facts below.

## Palette membership

Palette membership is optional and only runs when `palette=` is explicitly supplied.

The configured palette:

- is an ordered input sequence of exact RGBA8 colors,
- may contain 0..256 colors,
- rejects duplicate RGBA8 entries,
- is converted once to a packed membership set before the raster scan.

Membership applies only to structurally visible pixels (`alpha != 0`). The result records:

- configured palette size,
- visible pixel count,
- matching visible pixel count,
- non-matching visible pixel count,
- distinct non-matching visible color count,
- one exact `satisfied` boolean.

An empty configured palette is valid: it is satisfied only when the raster has no visible pixels.

This check does not create Q5-style findings or decide aesthetic palette quality.

## Maximum visible-color policy

`max_colors=` is optional and must be an exact integer in `[1, 256]`, matching the existing ArtIntent palette-budget range.

When configured, Q1 compares the exact visible RGBA8 color count with the requested limit and returns:

```text
{limit, actual_visible_colors, satisfied}
```

No maximum is silently assumed when the input is omitted.

## Transparent-RGB facts and policy

Q1 always records whether fully transparent pixels contain hidden non-zero RGB bytes:

```text
{nonzero_rgb_pixels, has_nonzero_rgb}
```

The fact is independent of policy. Hidden RGB does not make a pixel structurally visible and does not affect the visible palette count.

`transparent_rgb_policy=` is optional:

- `allow`: hidden non-zero RGB is explicitly accepted,
- `require_zero`: every `alpha == 0` pixel must also have `r == g == b == 0`.

The configured check returns the policy identity, exact violating-pixel count and `satisfied` boolean. Omitting the policy leaves the check as `null`.

## Complexity and memory

`analyze_color(canvas, ...)` performs one `O(width * height)` pass over the package-internal read-only RGBA view.

It does not call `Canvas.rgba_bytes()` and does not build a per-pixel object graph or coordinate collection.

For exact color cardinality it retains one packed-integer set of distinct visible RGBA8 colors: `O(k)`, where `k` is the number of distinct visible colors. When a palette is configured it additionally retains the bounded palette membership set (at most 256 packed integers) and a packed set of distinct non-member colors.

Using packed integers avoids tuple/object allocation for every scanned pixel while preserving exact RGBA8 identity.

## Scope boundary

P4-Q1 does not add:

- connectivity or isolated-pixel analysis,
- symmetry/outline diagnostics,
- tile-edge equality checks,
- typed severity/category/rule findings,
- universal aesthetic palette judgments,
- perceptual style/readability/identity claims,
- provider/model, VLM, GPU, image dependency, secret or self-hosted runner.

The next child after Q1 is P4-Q2 connectivity/isolation QA, but the core lane advances only after Q1 portable CI is green.
