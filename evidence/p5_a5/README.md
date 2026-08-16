# P5-A5 owner-triggered Codex CLI smoke

P5-A5 is the first opt-in real-provider execution. Normal repository correctness still uses the committed P5-A4 recorded provider; **GitHub-hosted CI must never run this smoke**.

## Resolved G3 boundary

The repository owner approved the following first real-provider boundary on 2026-08-16:

- provider surface: locally installed OpenAI Codex CLI invoked headlessly with `codex exec`,
- authentication/billing: existing **ChatGPT login only**; the runner refuses `codex login status` that reports API-key authentication,
- model: `gpt-5.6-sol`,
- reasoning effort: `low`,
- minimum Codex CLI: `0.144.0`,
- session: `--ephemeral`,
- sandbox: `read-only`, isolated temporary working directory,
- output: JSON-Schema-constrained `pixel_program` proposal followed by normal TracePixel validation,
- vision: off; no image is attached to Codex and no VLM/perceptual correctness gate is introduced,
- Agent loop budget: 4 iterations / 4 provider calls / 16 PixelProgram operations / 256 serialized pixel edits,
- cost boundary: no TracePixel-managed API key and no API-key-billed P5-A5 reference run; use the existing ChatGPT/Codex plan allowance.

The Codex adapter records `turn.completed.usage` token counts when the CLI exposes them. Dollar cost remains `null` because the authorized boundary is the existing ChatGPT plan rather than direct API billing.

## Run locally

From a TracePixel Git checkout with the package installed:

```powershell
codex --version
codex login status
python -m evidence.p5_a5.smoke
```

The smoke independently verifies the minimum CLI version and requires the login-status text `Logged in using ChatGPT` before any model request. It pins the model and reasoning effort itself; do not rely on the user's mutable Codex defaults.

The reference task asks Codex to author a 16x16 health-potion icon. TracePixel—not Codex—remains authoritative for proposal validation, mutation budgets, raster state, deterministic QA and PNG export.

## Evidence output

A successful run writes `evidence/p5_a5/reference-run/`:

- `manifest.json` — source commit, pinned provider settings, loop result and SHA-256 evidence,
- `telemetry.json` — P5-A3 complexity telemetry,
- `provider-calls.json` — final structured proposals plus token counts only; no hidden reasoning transcript,
- `final.rgba` — authoritative raster bytes,
- `final.png` — deterministic native PNG,
- `preview-8x.png` — nearest-neighbor human review preview.

P5-A5 is **not complete merely because this runner exists**. The child advances to P6 only after one owner-triggered real run succeeds, the resulting reference evidence is committed, and portable CI remains green without invoking Codex.
