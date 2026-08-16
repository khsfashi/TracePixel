# B0-B0 baseline-adapter checkpoint

This directory contains the provider-free acceptance checkpoint for the frozen B0-v1 method adapters.

Run:

```bash
python -m evidence.b0_b0.checkpoint
```

The checkpoint loads the exact B0-F0 preregistration, materializes the H0 schedule, and verifies that:

- all 28 primary attempt identities produce an adapter request;
- the frozen split remains 14 `tracepixel-staged-v1` and 14 `raw-pixel-program-v1` requests;
- both methods retain the same provider/model/auth and matched budget boundary;
- TracePixel requests carry staged context derived only from provider-visible task text;
- raw PixelProgram requests contain no staged/ArtIntent/observation context;
- hidden structural constraints do not enter provider-visible payloads;
- the dry Codex plan pins exact CLI `0.147.0`, ChatGPT auth, API-key rejection, read-only sandbox, model/reasoning settings, and 180-second provider timeout;
- provider invocations and scored attempts remain zero;
- owner gates G4, G5, and G6 remain uncrossed.

B0-B0 is adapter preparation only. The next child after green acceptance is B0-S0 scored visible-cohort execution under the already-frozen contract.
