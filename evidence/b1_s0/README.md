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

This checkpoint does not implement or execute the scored provider cohort. The next B1-S0 implementation must preserve the post-P7 completion contract: TracePixel cannot claim authoring completion until all six required stages are explicitly applied or skipped, bounded deterministic repair remains separate evidence, and B0 outputs are never used as B1 attempt inputs or substitutes.

Scored provider execution remains owner-triggered local/headless work and is never a portable-CI correctness gate.
