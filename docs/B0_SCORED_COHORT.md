# B0-S0 scored visible cohort

B0-S0 is the first provider-backed scored execution of the frozen B0 cohort. The runner in `evidence/b0_s0/run.py` is intentionally owner-local: it must use the exact Codex CLI / ChatGPT-auth boundary frozen by B0-F0 and it must not become a portable CI correctness gate.

## Frozen execution boundary

The runner loads `evidence/b0/preregistration.v1.json` and refuses to start unless the frozen contract remains compatible with the implementation.

Before the first new provider call it verifies:

- the frozen `repository_commit_under_test` exists locally;
- production `src/tracepixel/{agent,model,qa,raster}` content still matches that frozen commit;
- those production paths have no local tracked or untracked changes;
- every hidden deterministic rule has an implemented scorer;
- every scheduled request can be constructed without exposing `hidden_structural_constraints`;
- Codex reports exactly `codex-cli 0.147.0`;
- `codex login status` reports `Logged in using ChatGPT` and not API-key auth.

Benchmark infrastructure added after the commit-under-test lives under `src/tracepixel/benchmark`, `evidence/b0_s0`, tests and docs. It may orchestrate the frozen architecture but must not silently improve the production implementation under test.

## Cohort policy

The primary schedule remains the preregistered 7 tasks × 2 scored methods × 2 trials = 28 attempts. The runner exposes no task/method subset flag, so normal execution cannot cherry-pick a favorable slice.

For each attempt:

1. build the matched visible request for the scheduled method;
2. invoke the exact frozen Codex plan;
3. allow one identical-request retry only when transport/provider execution returns no usable proposal bytes, consuming provider-call budget;
4. validate the method-specific response and cumulative PixelProgram budgets;
5. execute the accepted PixelProgram deterministically into a fresh authoritative canvas;
6. run the frozen deterministic structural checks;
7. stop immediately if all deterministic rules pass, otherwise feed only task-applicable deterministic failed checks into the next bounded revision;
8. stop at any frozen provider/iteration/operation/pixel-edit/tool/wall-time boundary without an appearance-based decision.

The TracePixel method advances `current_stage` deterministically through the canonical stage sequence for successive logical iterations. The full canonical stage sequence is present in every staged authoring surface; the four-call budget is not widened to manufacture six separate stage calls.

A harness-valid final raster counts as completion even when one or more deterministic rules fail. A non-completing attempt contributes zero structural fraction, as frozen. Failures are retained; the runner does not repair, delete or selectively rerun them.

## Evidence retention

Every scheduled attempt is written through the B0-H0 immutable writer under:

`evidence/b0/results/<freeze-commit>/<method>/<task>/<trial>/`

Required files are:

- `attempt-manifest.json`
- `provider-request.json`
- `provider-response.json`
- `proposal-or-failure.json`
- `deterministic-qa.json`
- `telemetry.json`

Completed attempts additionally retain `final.rgba`, `final.png`, and `preview-8x.png`.

Provider response retention contains schema output, token usage, known tool-call counts, return status and stable error codes. Raw stderr is deliberately not published so local paths or incidental machine details are not leaked into the public repository. API cost remains `null` under the frozen ChatGPT-auth boundary instead of being guessed.

A partial run may be resumed only when every existing attempt directory already contains a valid immutable manifest and the runner commit is unchanged. An incomplete attempt directory blocks automatic resume because overwriting or rerunning a possibly invoked provider call would violate the preregistered exclusion policy.

## Blind owner review package

After all scheduled attempts have immutable manifests, the runner creates a separate package under:

`evidence/b0/review/<freeze-commit>/`

Completed previews are copied to method-neutral filenames and ordered within each task by the frozen SHA-256 key:

`<task_id>|<trial_index>|<method_id>`

The review manifest omits method labels and names the three frozen 1–5 dimensions: recognizability, native-1x readability and style coherence. Human scores are not written by the provider runner; B0-P0 consumes the owner review record without changing deterministic attempt results.

## Running the real cohort

Portable CI runs only the provider-free B0-S0 checkpoint. The real cohort requires an owner machine with the frozen Codex CLI and existing ChatGPT login:

```bash
python -m evidence.b0_s0.run
```

Do not run the real cohort merely to test the script. Once the first provider invocation occurs, B0's scored cohort has started and the frozen no-cherry-picking / no-post-hoc-repair policy applies.

## Completion boundary

Merging the runner does **not** complete B0-S0. `current_child` stays `B0-S0` until the 28 scheduled attempts, generated cohort summary and blind owner review evidence are retained. Only then may the project advance to B0-P0.
