# Codex CLI real-provider boundary

P5-A5 deliberately connects the provider-neutral Agent seam to a real network model without adding an OpenAI SDK, API key, or network requirement to the core package or portable CI.

```text
bounded AgentProviderRequest
  -> CodexCliProvider
  -> isolated `codex exec` subprocess
  -> schema-constrained candidate PixelProgram
  -> existing provider validation
  -> A2 budget preflight / deterministic execution
  -> deterministic Q5 QA
  -> A3 complexity telemetry
```

## Authority and isolation

`CodexCliProvider` never receives raster authority. It serializes the already-bounded P5-A1 request to stdin and runs Codex in an ephemeral, read-only temporary directory. The prompt explicitly forbids filesystem inspection and shell use; the sandbox is a second containment boundary rather than a correctness assumption.

The final Codex message is constrained to the PixelProgram proposal shape. TracePixel still performs its normal runtime validation after parsing the JSON. Structured output is therefore an adapter reliability aid, not a replacement for P2 validation.

No repository path, transcript history, full canvas bytes, image attachment, API secret, or mutable SDK object is sent by the adapter. P5-A1's compact observation remains the model-visible state boundary.

## Owner gate G3 resolution

For the first reference smoke the owner pins:

```text
provider surface: OpenAI Codex CLI
model: gpt-5.6-sol
reasoning effort: low
minimum CLI: 0.144.0
auth: existing ChatGPT login only
vision: off
session: ephemeral
sandbox: read-only
loop budget: 4 iterations / 4 calls / 16 operations / 256 pixel edits
direct API billing: not authorized for the P5-A5 reference run
```

The adapter checks `codex login status` and refuses API-key authentication. This keeps the cost envelope at the existing ChatGPT/Codex plan allowance and prevents TracePixel from silently introducing a separately billed API credential.

G4 remains unresolved because no image/VLM input or perceptual score is used.

## Telemetry

`codex exec --json` exposes a `turn.completed` usage object. The adapter maps available input/output token counts into `AgentProviderUsage`, allowing the existing A3 wrapper to aggregate them across bounded revisions. Cached/reasoning token details are not promoted into the v1 telemetry schema, and API-dollar cost remains unknown/null under the ChatGPT-plan boundary.

The reference evidence stores only final proposals and usage counts. It does not persist Codex reasoning streams.

## CI rule

Portable CI tests the adapter with a fake subprocess runner. It does not require Codex installation, authentication, network access, secrets, or a paid provider. The actual `evidence.p5_a5.smoke` command is owner-triggered locally only.
