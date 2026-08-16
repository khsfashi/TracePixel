# B0-P0 Immutable Postmortem

B0 is complete as **development-visible matched architecture evidence**. The scored cohort is frozen and must not be rerun, relabelled, or selectively repaired to improve the recorded B0 result.

## Frozen evidence

- preregistration freeze: `c4b31288867fd4c4cf5ea3664808bd6f47cca1db`
- repository commit under test: `7fd1a3a0f952203d1875e802c89c3ab6e3750611`
- scored runner commit: `75aeb62b5e852751d80e4d26ae98841366a3ea5c`
- scheduled / retained attempts: **28 / 28**
- infrastructure voids: **0**
- owner blind ratings: **28 / 28**
- blind review manifest SHA-256: `b0ac5f3cb939c83cfd5fe9692eee298a3dd8a1c3c45ec3652b1d450e5eae3c69`

Machine-readable authority is `evidence/b0/postmortem.v1.json`. The underlying cohort and review records remain separately retained under `evidence/b0/results/` and `evidence/b0/review/`.

## Layered result

B0 intentionally does **not** compute a composite winner.

| Layer | `raw-pixel-program-v1` | `tracepixel-staged-v1` |
|---|---:|---:|
| completed | 14 / 14 | 14 / 14 |
| structural pass rate | 1.000 | 1.000 |
| mean structural fraction | 1.000 | 1.000 |
| mean input tokens | 16,731.14 | 15,919.43 |
| mean output tokens | 1,450.29 | 1,297.36 |
| mean iterations | 1.0714 | 1.0000 |
| mean changed pixels | 89.07 | 81.07 |
| mean wall time | 33,391 ms | 29,983 ms |
| owner recognizability mean | **4.5000** | **2.7857** |
| owner native-1x readability mean | **4.5000** | **2.7857** |
| owner style-coherence mean | **4.5714** | **3.0714** |
| human rejections | **0 / 14** | **5 / 14** |

The five staged-method human rejections were concentrated in:

- `B0-T1-01` potion: 2 / 2 staged trials,
- `B0-T2-02` lantern: 1 / 2 staged trials,
- `B0-T3-01` barrel: 2 / 2 staged trials.

These are **human perceptual rejections**, not deterministic failures. Both methods still satisfied every frozen structural rule on every completed attempt.

## Primary diagnosis: the staged stop condition was wrong

The B0 runner selected the staged method's `current_stage` from the logical iteration index:

```text
silhouette
 -> major_forms
 -> palette_light_ramp
 -> shading
 -> semantic_details
 -> outline_cleanup
```

However, after each accepted proposal the scored loop stopped immediately when global deterministic QA reported `all_rules_pass == true`.

That made structural correctness double as an authoring-completion signal. In B0 this was especially damaging because `tracepixel-staged-v1` averaged exactly **1.0 iteration** and **0 revisions** across all 14 trials. The controller therefore never advanced to a later stage-loop context after the initial `silhouette` iteration.

A model was still free to put more detail into its silhouette proposal, but the architecture did not guarantee that the remaining authored stages were applied or explicitly skipped. B0 shows that this distinction matters: global structural correctness was 100% while owner-visible quality diverged strongly.

## Complexity interpretation

The staged method used fewer tokens, changed fewer pixels, and finished faster on average. B0 does **not** treat that as an efficiency win.

Those lower costs are confounded by the same premature stop condition: the staged method frequently ended before later authoring work could occur. A system that does less authoring can look cheaper while producing worse human-visible output.

Future telemetry therefore needs explicit stage coverage/final-stage evidence in addition to token, operation, revision, pixel-change, and wall-time metrics.

## Failure classification

- provider / transport / execution failures: **0**
- infrastructure voids: **0**
- deterministic structural failures at completion: **0**
- human perceptual rejections: **5**, all in `tracepixel-staged-v1`

The B0 result does not justify hiding those perceptual failures behind the 100% structural score, nor does it justify converting human preference into deterministic truth.

## Architecture follow-ups

The frozen B0 evidence selects the following changes. They happen **after B0**.

1. **Separate staged authoring completion from global structural QA.** Required stages must be applied or explicitly skipped before final authoring completion. A structural pass may stop deterministic repair work, but it must not silently terminate the authored stage plan.
2. **Version feedback/finding intake in P7.** Deterministic QA facts and owner perceptual feedback remain separate authorities, with explicit source/provenance and bounded stage/region hints.
3. **Localize before repair.** Map a finding or owner feedback item to the affected stage/region before producing a bounded minimal repair PixelProgram.
4. **Measure actual repair and stage coverage.** Record stage coverage, changed pixels, changed operations, revision cost, and unaffected-region stability so under-authoring cannot masquerade as efficiency.
5. **Use held-out B1 for the next score.** Do not rerun B0 after these changes. B1 must be newly preregistered and held out.

These follow-ups are tracked by P7 issue #71.

## Claim boundary

B0 supports these statements:

- the matched harness and retention path worked end to end,
- both methods achieved the frozen deterministic structural requirements in this visible cohort,
- the raw PixelProgram baseline received materially stronger owner-blind perceptual ratings in this cohort,
- the staged controller's completion semantics need architectural repair before a held-out benchmark.

B0 does **not** support a universal pixel-art quality claim, a composite winner claim, or a claim that the current TracePixel staged architecture is perceptually superior.

No G4 VLM judge, G5 Aseprite/MCP scored baseline, or G6 self-hosted benchmark execution was silently enabled.
