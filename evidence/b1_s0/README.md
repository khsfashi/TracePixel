# B1-S0 Scored Cohort Guard

This directory owns the provider-free safety boundary that must be green before the first B1 scored provider invocation.

The B1-F0 freeze is anchored at:

```text
ca612a026ff5e74c397d9aa4ef8c0bdb25d1df6a
```

The production architecture under test remains the preregistered P7 -> B1 handoff commit:

```text
0ee45b1e466d4d1ec4e077b835ae31d47a1379a1
```

`python -m evidence.b1_s0.checkpoint` verifies:

- the exact recorded B1-F0 freeze commit,
- the frozen preregistration and scored method identities,
- B1 task IDs and visible task text remain held out from frozen B0,
- the exact 28 primary attempt identities implied by 7 tasks x 2 methods x 2 trials,
- result paths are rooted under the recorded B1 freeze commit and do not cross the B0 result boundary,
- the live core lane is `B1 / B1-S0 / #79`,
- no provider is invoked by the checkpoint.

The provider-free scored-result contract in `tracepixel.benchmark.b1_scored` additionally enforces:

- unsuccessful TracePixel attempts may retain a fixed-order prefix of stage decisions,
- `completion=true` for `tracepixel-post-p7-v1` is impossible until all six frozen stages are explicitly `applied` or `skipped`,
- applied/skipped counts and authoring completion are retained as stage evidence rather than folded into deterministic structural QA,
- bounded P7 repair evidence is retained in a distinct repair layer and is unavailable to the raw baseline,
- deterministic QA, stage coverage, repair evidence, and complexity telemetry remain distinct result layers,
- retained B1 result-layer payloads reject references into `evidence/b0/results/` so a B0 attempt cannot be used as a scored B1 seed or substitute.

This checkpoint and completion contract do not invoke the scored provider cohort. The next B1-S0 implementation should bind the frozen Codex adapter/executor to these identities and result layers, then execute the 28 owner-triggered local/headless attempts without mutating the frozen cohort.

Scored provider execution remains owner-triggered local/headless work and is never a portable-CI correctness gate.
