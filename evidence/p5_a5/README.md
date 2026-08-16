# P5-A5 owner-triggered Codex CLI smoke

P5-A5 is the first opt-in real-provider execution. Normal repository correctness still uses the committed P5-A4 recorded provider; **GitHub-hosted CI must never run this smoke**.

## Resolved G3 boundary

The repository owner approved the following first real-provider boundary on 2026-08-16:

- provider surface: OpenAI Codex CLI invoked headlessly with `codex exec`,
- authentication/billing: existing **ChatGPT login only**; the runner refuses `codex login status` that reports API-key authentication,
- model: `gpt-5.6-sol`,
- reasoning effort: `low`,
- minimum adapter-compatible Codex CLI: `0.144.0`,
- automated reference-run Codex CLI: `0.147.0`, installed only under the Actions runner temporary directory,
- session: `--ephemeral`,
- sandbox: `read-only`, isolated temporary working directory,
- output: JSON-Schema-constrained `pixel_program` proposal followed by normal TracePixel validation,
- vision: off; no image is attached to Codex and no VLM/perceptual correctness gate is introduced,
- Agent loop budget: 4 iterations / 4 provider calls / 16 PixelProgram operations / 256 serialized pixel edits,
- cost boundary: no TracePixel-managed API key and no API-key-billed P5-A5 reference run; use the existing ChatGPT/Codex plan allowance.

The Codex adapter records `turn.completed.usage` token counts when the CLI exposes them. Dollar cost remains `null` because the authorized boundary is the existing ChatGPT plan rather than direct API billing.

## Automated owner runner

`.github/workflows/owner-codex-smoke.yml` runs only on the explicitly trusted owner Windows runner. It always checks out `main`, prepares the pinned job-local Codex CLI, reuses the Windows user's existing ChatGPT authentication, runs the smoke, and uploads evidence as an Actions artifact. The owner's global Codex installation is not replaced or upgraded.

Normal pull-request CI remains GitHub-hosted and provider-free.

## Run locally

A direct local run is still available from a TracePixel Git checkout with a compatible Codex CLI:

```powershell
codex --version
codex login status
python -m evidence.p5_a5.smoke
```

The smoke verifies the minimum CLI version and requires the login-status text `Logged in using ChatGPT` before any model request. It pins the model and reasoning effort itself; do not rely on the user's mutable Codex defaults.

The reference task asks Codex to author a 16x16 health-potion icon. TracePixel—not Codex—remains authoritative for proposal validation, mutation budgets, raster state, deterministic QA and PNG export.

## Committed reference run

The first successful reference run is frozen from owner workflow run `31920954315` against source commit `c53d934cb6296c27e29455734c747363d9c8254b`.

It completed in one provider call and one loop iteration with one PixelProgram operation containing 96 pixel edits. Deterministic QA finished with zero findings. Complexity evidence recorded 16,000 input tokens, 1,417 output tokens, zero visual-observation calls, zero human interventions and no failure category. The resulting 16x16 raster uses six visible colors and is replayable byte-for-byte from the committed provider proposal.

This is a **non-scored architecture/reference smoke**, not an aesthetic benchmark. No perceptual/VLM score is asserted and G4 remains unresolved.

## Evidence output

The committed `evidence/p5_a5/reference-run/` contains:

- `manifest.json` — source commit, pinned provider settings, loop result and SHA-256 evidence,
- `telemetry.json` — P5-A3 complexity telemetry,
- `provider-calls.json` — final structured proposal plus token counts only; no hidden reasoning transcript,
- `final.rgba` — authoritative raster bytes,
- `final.png` — deterministic native PNG,
- `preview-8x.png` — nearest-neighbor human review preview.

`tests/test_p5_a5_evidence.py` remains provider-free: it validates the committed telemetry/proposal, replays the PixelProgram, and requires exact RGBA/native-PNG/preview-PNG bytes. No future portable CI run calls Codex to verify this evidence.
