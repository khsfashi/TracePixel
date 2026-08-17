# B1 Held-out Preregistration

B1-F0 freezes the first held-out generalization cohort for the post-B0/P7 TracePixel architecture. No scored B1 provider run may begin until the commit on `main` that first contains `evidence/b1/preregistration.v1.json` is recorded as the B1 freeze commit.

The machine-readable authority is `evidence/b1/preregistration.v1.json`. This document explains the intent; it does not replace the frozen JSON.

## What is under test

The repository commit under test is:

```text
0ee45b1e466d4d1ec4e077b835ae31d47a1379a1
```

That commit is the explicit P7 -> B1 lane handoff and includes the completed P7 contracts. B1 therefore evaluates the post-P7 architecture rather than mutating or rerunning the B0 implementation.

The scored comparison is:

```text
tracepixel-post-p7-v1
vs
raw-pixel-program-v1
```

Both use the same ChatGPT-authenticated Codex CLI provider boundary, `gpt-5.6-sol`, low reasoning effort, no vision input, and the same visible B1 task text. TracePixel alone receives its stage/localization/repair surface because that is the architecture being tested; the raw method receives only the low-level PixelProgram surface plus the same task-applicable deterministic QA facts.

## Held-out boundary

B0 remains immutable.

B1 uses seven newly frozen task IDs and visible task texts across T0-T3. None may equal a B0 task ID or visible task text. Scored B1 execution may not read, copy, seed from, transform, relabel, or substitute B0 final RGBA/PNG outputs.

B0's postmortem is allowed to inform the architecture and benchmark design. Its attempt outputs and owner scores are not B1 scored evidence.

This keeps the intended sequence explicit:

```text
B0 evidence
 -> P7 architecture changes
 -> newly frozen B1 tasks
 -> new B1 attempts only
```

## Why the B1 budget is larger than B0

B0 exposed a controller confound: the staged method could stop after `silhouette` as soon as global deterministic QA passed. P7 requires required authoring stages to be explicitly applied or skipped before authoring completion.

B1 therefore freezes up to eight provider/iteration/tool calls and 2,048 cumulative pixel edits per trial. That ceiling is still finite, is identical for both scored methods, and leaves enough headroom for the six staged authoring steps plus bounded repair. The larger ceiling is not a promise that every trial should consume it.

Two trials per task per method remain frozen, producing 28 scheduled scored attempts:

```text
7 tasks * 2 methods * 2 trials = 28 attempts
```

## Authority layers stay separate

B1 does not define a composite winner.

The retained result layers are:

- completion,
- deterministic structural fraction/pass,
- TracePixel stage coverage,
- repair cost/evidence where applicable,
- Agent complexity,
- blind owner perceptual review.

A TracePixel trial cannot claim authoring completion until every required stage is explicitly applied or skipped, but stage coverage is not folded into the deterministic structural fraction.

The owner blind-rates recognizability, native-1x readability, and style coherence on the same 1-5 scale used in B0. Human ratings never override deterministic QA.

## Human feedback scope

P7 supports bounded owner feedback, but B1-v1 deliberately disables human intervention during generation. The owner performs only the frozen blind post-generation review.

This isolates the post-P7 autonomous architecture from selective interactive hints. A future interactive repair study would need its own frozen matched protocol rather than being silently added to B1-v1 after results are visible.

## Owner gates

B1-F0 does not cross unresolved gates:

- G4 VLM/perceptual judge: disabled,
- G5 Aseprite/MCP scored baseline: excluded,
- G6 self-hosted runner: not used.

B1-F0 also does not promote humanoids, animation, Trace2D integration, or other later product scope.

## Retention and failure policy

Every scheduled attempt is retained, including invalid output, deterministic rejection, provider failure, timeout, budget exhaustion, semantic/human rejection, and infrastructure-void records.

Scored evidence belongs under:

```text
evidence/b1/results/<freeze-commit>/<method>/<task>/<trial>/
```

Authentication material and secrets are never retained. Failed/non-completing attempts remain in denominators; B0 attempts cannot substitute for B1 attempts.

## Handoff

After this freeze merges green, record its exact merge commit as the B1-F0 freeze commit before any scored provider invocation. Then begin **B1-S0 multiple-trial scored cohort** only.

Do not edit this cohort after scoring begins to improve TracePixel's result. Any architecture change after the freeze belongs after B1-P0 or in a separately preregistered benchmark.
