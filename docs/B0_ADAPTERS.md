# B0 frozen method adapters

B0-B0 wires the two methods already frozen by B0-F0 into the common B0-H0 attempt/result harness. It is deliberately provider-free: this child materializes and validates the exact request/response contracts and Codex CLI execution recipe, but it does not start any of the 28 scored attempts.

The authoritative preregistration freeze remains `c4b31288867fd4c4cf5ea3664808bd6f47cca1db`. No task text, hidden structural constraint, provider/model setting, budget, trial count, scoring rule, retry/exclusion rule, or retention rule is changed here.

## Exactly two scored adapters

B0-B0 accepts only the frozen method order:

1. `tracepixel-staged-v1` / `tracepixel-staged-agent`
2. `raw-pixel-program-v1` / `raw-primitive-agent`

Both adapters pin the same provider boundary from B0-F0:

- OpenAI Codex CLI through the existing ChatGPT-authenticated session;
- exact frozen CLI identity `codex-cli 0.147.0`;
- model `gpt-5.6-sol`;
- reasoning effort `low`;
- vision disabled;
- read-only sandbox;
- ephemeral execution;
- no separately billed API-key authentication.

The dry execution plan records `codex --version`, `codex login status`, the exact expected version string, the required `Logged in using ChatGPT` marker, and the prohibition on API-key auth. The scored B0-S0 runner must enforce these checks before provider invocation.

## Matched information and budgets

Every request is anchored to an H0 attempt identity and obtains its task through `visible_task_packet()`. Therefore the provider-visible task portion contains only the frozen task ID, tier, and exact `visible_text`; `hidden_structural_constraints` is recursively forbidden from adapter payloads and feedback.

Both methods carry the same frozen provider settings and the same matched limits for provider calls, iterations, tool calls, operations, cumulative pixel edits, visual observations, reported input/output tokens, provider timeout, trial wall timeout, and human interventions.

The initial deterministic-feedback envelope is explicitly unavailable rather than pretending that an empty finding list is a passing QA result. After an accepted revision, B0-S0 may replace it with the same task-applicable deterministic QA facts for either method.

## TracePixel staged method

`tracepixel-staged-v1` receives the architecture-specific surface that B0 is testing:

- the canonical P3 six-stage sequence;
- a current stage identity;
- the Agent proposal envelope;
- a compact B0 observation seed carrying current-stage identity and deterministic feedback;
- an ArtIntent derived only from information literally present in the frozen visible task.

The visible-task-to-ArtIntent adapter extracts the explicit canvas size and palette budget and, when literally stated, facing and required symmetry. It intentionally leaves occupied bounds and light direction null instead of inferring additional structure. The derived ArtIntent is run through the existing `validate_art_intent()` contract before it can enter a request.

B0-B0 does **not** equate the six P3 stage names with six provider calls. B0-F0 permits at most four provider calls per trial. Stage identity is method context; the B0-S0 runner must remain within the frozen four-call budget and may not widen it to visit every stage with a separate call.

## Raw PixelProgram method

`raw-pixel-program-v1` receives only:

- the same visible task;
- the same provider and budgets;
- the same deterministic-feedback envelope;
- the v1 `PixelProgram` surface with only `set_pixels` operations.

Its provider payload contains no stage key, no ArtIntent key, no observation key, and no negative wording explaining which TracePixel features are absent. This avoids giving the raw baseline an accidental method-description hint beyond its actual authoring surface.

The raw method returns a direct `tracepixel.pixel-program.v1`. The staged method returns the existing `tracepixel.agent-provider-proposal.v1` pixel-program envelope. `normalize_b0_provider_output()` reduces both to the same PixelProgram boundary and validates the result with the existing PixelProgram validator before later deterministic execution.

## Provider-free checkpoint

`python -m evidence.b0_b0.checkpoint` verifies that all 28 frozen primary identities can be materialized as adapter requests, split 14/14 between the two methods, without invoking a provider. It also verifies the frozen provider/auth/version/timeout boundary, the absence of hidden constraints, staged-only context, raw-surface isolation, and that G4/G5/G6 remain uncrossed.

Portable CI may run this checkpoint because it performs no network/provider invocation. Actual scored generation remains the next child, **B0-S0**. B0-S0 must retain every attempt through H0, including failures, and may not silently introduce VLM judging, Aseprite/MCP, or a self-hosted runner.
