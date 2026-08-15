# Compact Agent observation

P5-A1 freezes the provider-neutral state sent for one next-decision request. The contract is intentionally narrower than a transcript, full Canvas dump, or replay history.

`tracepixel.agent-observation.v1` contains exactly:

- validated P3 `ArtIntent`,
- current stage plus non-negative revision,
- P4-Q5 typed findings only,
- optional bounded PNG preview evidence,
- at most four recent revision summaries.

The normal builder accepts no `Canvas` and no historical transcript, so those large authority surfaces cannot be accidentally serialized into the default provider request.

## Contract

```json
{
  "schema": "tracepixel.agent-observation.v1",
  "intent": {
    "schema": "tracepixel.art-intent.v1",
    "asset_class": "icon",
    "canvas": {"width": 16, "height": 16},
    "composition": {
      "occupied_bounds": null,
      "facing": null,
      "symmetry": null,
      "light_direction": null,
      "palette_budget": 8
    }
  },
  "current": {"stage": "semantic_details", "revision": 3},
  "qa": {
    "schema": "tracepixel.qa-findings.v1",
    "findings": []
  },
  "preview": null,
  "recent": [
    {
      "revision": 2,
      "stage": "shading",
      "proposal_kind": "pixel_program",
      "operation_count": 1,
      "changed_pixels": 12
    }
  ]
}
```

`intent` delegates to the existing ArtIntent validator. `qa` carries only stable Q5 `{rule, category, severity}` records; raw Q0-Q4 raster facts are not duplicated into every provider request.

Recent records are ordered, must precede the current revision, and are bounded to four entries. They contain counts and identities only, not complete PixelPrograms, StagePlans, provider messages, or earlier observations.

## Preview boundary

Preview data is opt-in. When supplied it must be PNG-signature data, SHA-256 self-consistent, and at most 64 KiB decoded. The builder base64-encodes those bytes only for the provider-neutral JSON envelope.

No preview is emitted by default. This preserves a cheap text-only path for decisions that do not need visual evidence and prevents repeated image resend from becoming implicit behavior.

Preview evidence is not authoritative raster truth and does not introduce a perceptual correctness score. G4 remains untouched.

## Complexity and allocation

Validation is bounded by the small ArtIntent object, at most ten Q5 findings, at most four recent summaries, and at most 64 KiB preview bytes. The builder makes bounded defensive copies of the small summaries so later caller mutation cannot alter an already-built observation.

There is no raster-sized allocation unless the caller explicitly opts into preview bytes, and even that path is capped. No provider SDK, network object, model identity, retry state, API key, or transcript object is accepted.

## Deferred to later P5 children

P5-A1 does not implement:

- iteration/finish/revise orchestration — P5-A2,
- token/cost/wall-time telemetry — P5-A3,
- recorded/fake-provider orchestration CI — P5-A4,
- a live provider/model adapter — P5-A5 / G3,
- perceptual/VLM correctness — G4.
