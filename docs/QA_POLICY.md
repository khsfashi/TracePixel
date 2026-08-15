# Typed QA Findings and Policy

P4-Q5 is the classification layer above the deterministic Q0-Q4 fact surfaces.

It does **not** inspect raster pixels, invoke analyzers, choose art constraints, or judge aesthetics. Its only job is to apply an explicit ordered policy to already-computed deterministic facts and emit stable machine-readable findings.

```text
Canvas
  -> Q0 structural facts ---------\
  -> Q1 color facts/checks --------\
  -> Q2 connectivity facts ---------+-> explicit Q5 policy -> typed findings
  -> Q3 shape/outline facts --------/
  -> Q4 tile-edge facts -----------/
```

## Stable schemas

Policy input:

```json
{
  "schema": "tracepixel.qa-policy.v1",
  "rules": [
    {"rule": "structural.non_empty", "severity": "error"},
    {"rule": "color.maximum_colors", "severity": "warning"}
  ]
}
```

Finding output:

```json
{
  "schema": "tracepixel.qa-findings.v1",
  "findings": [
    {
      "rule": "color.maximum_colors",
      "category": "color",
      "severity": "warning"
    }
  ]
}
```

The policy order is authoritative. Each selected rule emits at most one finding, and passing rules emit nothing. The engine owns the rule-to-category mapping; callers choose only which rule is active and its severity. Duplicate rule IDs are rejected instead of being merged or reordered.

Supported severities are `info`, `warning`, and `error`. Severity is policy metadata, not a property of a raw raster fact.

## Rule identities

| Rule | Category | Source | Failure condition |
| --- | --- | --- | --- |
| `structural.non_empty` | `structural` | Q0 | raster is structurally empty |
| `structural.no_translucency` | `structural` | Q0 | at least one pixel has alpha in `1..254` |
| `structural.no_edge_contact` | `structural` | Q0 | visible content touches any canvas edge |
| `color.palette_membership` | `color` | Q1 | explicitly configured palette-membership check is unsatisfied |
| `color.maximum_colors` | `color` | Q1 | explicitly configured maximum-color check is unsatisfied |
| `color.transparent_rgb_policy` | `color` | Q1 | explicitly configured transparent-RGB check is unsatisfied |
| `connectivity.single_component` | `connectivity` | Q2 | visible 4-connected component count is not exactly one |
| `connectivity.no_isolated_pixels` | `connectivity` | Q2 | at least one visible isolated pixel exists |
| `shape.required_symmetry` | `shape` | Q3 | any explicitly requested symmetry axis mismatches |
| `tile.contract` | `tile` | Q4 | explicitly configured edge/corner tile contract is unsatisfied |

Q5 never invents the parameters for Q1, Q3, or Q4. Selecting one of those rules without its upstream explicit check is a deterministic `missing_explicit_check` evaluation error. A missing or wrong fact schema is a deterministic `missing_or_invalid_fact` evaluation error.

## Runtime and allocation boundary

`evaluate_qa_policy()` accepts no `Canvas` and performs no raster scan or copy.

For `R <= 10` unique v1 rules:

- runtime is `O(R)`,
- auxiliary evaluation state is `O(1)` apart from the output list,
- output allocation is `O(F)` for `F <= R` failed rules,
- Q0-Q4 fact objects are borrowed and not normalized, copied, or mutated.

Raster costs therefore remain owned by the analyzers that produced the facts. Re-running policy with different severities does not re-read pixels.

## Deterministic versus perceptual responsibility

Deterministic policy findings may report only facts that follow exactly from the Q0-Q4 contracts plus explicit caller requirements.

The following remain outside Q5 deterministic truth:

- whether the asset is attractive,
- whether a sprite reads clearly at game scale,
- whether it looks like the requested identity or character,
- whether an outline is stylistically pleasing,
- whether asymmetry or isolated pixels are artistically desirable when no explicit rule forbids them,
- general style coherence or aesthetic quality.

Those belong to later perceptual/VLM evidence and final human judgment. A future perceptual score must not silently become a Q5 rule.

## Seeded checkpoint

`evidence/p4_q5/` commits one clean 5x5 fixture and one deliberately defective 5x5 fixture. The defect fixture seeds exact failures across structural, color, connectivity, required-symmetry, and tile-contract rules while keeping the raw fact analyzers unchanged.

The checkpoint is covered by `tests/test_qa_policy.py` and `tests/test_p4_q5_evidence.py`. Its committed manifest freezes the policy order and expected typed findings; `preview.svg` places the clean and defective rasters beside the finding summary for human inspection.
