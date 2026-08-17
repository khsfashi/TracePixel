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

The B1-specific Codex boundary in `tracepixel.benchmark.b1_adapters` now binds the frozen cohort to owner-local/headless execution without invoking the scored provider in portable CI:

- both scored methods are pinned to the exact B1-F0 Codex/model/auth/sandbox settings,
- every provider-visible request contains only the frozen visible task packet and rejects hidden constraints or `evidence/b0/results/` references,
- TracePixel receives the six-stage post-P7 authoring/repair surface while the raw baseline cannot receive stage or repair guidance,
- all 28 frozen attempt identities materialize unique retention roots under `evidence/b1/results/<B1-F0-freeze>/...`,
- Codex preflight requires exactly `codex-cli 0.147.0`, ChatGPT authentication, no API-key authentication, read-only sandboxing, and ephemeral execution,
- response schemas normalize both methods to the same PixelProgram v1 surface while retaining Codex call usage/tool telemetry separately.

The provider-free scored runner in `tracepixel.benchmark.b1_runner` now closes the remaining execution-loop boundary before real B1 scoring:

- TracePixel consumes all six frozen authoring stages in order even if deterministic structural QA passes at an earlier stage, preventing the B0 early-stop/under-authoring confound from recurring,
- each accepted provider response is evaluated as one complete PixelProgram candidate under the frozen 8-call / 2,048-pixel-edit ceiling rather than being silently accumulated as an unfrozen ninth authoring surface,
- zero-edit TracePixel stage responses are retained as explicit `skipped` decisions without erasing the last valid artifact, while nonzero valid responses are retained as `applied`,
- only after all six stage decisions are complete may TracePixel spend remaining frozen call/edit headroom on deterministic-feedback-driven post-stage revision/repair attempts,
- the raw baseline receives no TracePixel stage or repair guidance and may stop on the first structurally passing harness-valid candidate,
- provider requests, provider responses, final deterministic QA, complexity telemetry, final raster/PNG evidence, and the `b1_scored` attempt record are retained separately under the exact B1 freeze-root attempt identity,
- retention refuses to overwrite an already-claimed attempt directory and writes a SHA-256/byte-count index for the retained payloads,
- post-stage repair-cycle telemetry does not fabricate P7 `tracepixel.repair-evidence.v1`; that distinct evidence layer remains unavailable unless an actually validated P7 repair-evidence bundle is produced.

The owner-local cohort entrypoint is `python -m evidence.b1_s0.run`. It is deliberately fail-closed and requires one explicit mode:

```text
python -m evidence.b1_s0.run --preflight-only
python -m evidence.b1_s0.run --run-scored-cohort
```

`--preflight-only` validates the frozen/held-out boundaries, clean frozen production-source boundary, all 28 provider requests, exact Codex CLI version, ChatGPT authentication, model/settings, and runner commit without invoking a scored provider call or writing scored attempts.

`--run-scored-cohort` is the explicit owner arm for real scoring. Before every new provider attempt it writes and fsyncs a durable claim under `evidence/b1/results/<freeze>/.claims/`. Automatic resume is allowed only for attempts whose final `retention-index.json` exists and whose indexed required payloads still match their retained SHA-256 and byte counts. A claim without complete validated retention blocks automatic rerun because the provider may already have been invoked. Fully retained attempts may be skipped only when their recorded runner commit exactly matches the current runner commit.

After all 28 frozen attempts are retained, the entrypoint writes a method-separated cohort summary and a method-blind owner review package under `evidence/b1/review/<freeze>/`, ordered by the frozen SHA-256 rule and carrying the preregistered human dimensions/scale. No VLM judging, Aseprite/MCP baseline, self-hosted runner, prompt edit, manual pixel edit, or human hint is introduced.

Run real scoring only from the merged guard commit on a clean owner-local/headless checkout. If a durable claim blocks resume, do not delete it merely to obtain another scored sample; adjudicate the pre-invocation infrastructure state under the frozen exclusion policy instead.

All portable tests for this entrypoint use fake transports only. The real 28-attempt provider cohort remains owner-triggered local/headless work and is never a portable-CI correctness gate. After generation and the frozen owner review are complete, B1-S0 can hand off to B1-P0 generalization postmortem work.
