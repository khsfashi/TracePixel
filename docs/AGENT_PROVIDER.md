# Provider-neutral Agent interface

P5-A0 introduces the first replaceable model boundary without selecting a provider, model, SDK, retry policy, network transport, or cost envelope.

The authority direction remains:

```text
provider-neutral request
  -> provider proposal
  -> existing PixelProgram / StagePlan validation
  -> later deterministic orchestration
  -> deterministic raster + QA authority
```

A provider proposal is candidate data only. It never becomes canonical raster or Pixel IR truth merely because a model or adapter returned it.

## Request v1

`tracepixel.agent-provider-request.v1` is a closed JSON-compatible envelope:

```json
{
  "schema": "tracepixel.agent-provider-request.v1",
  "instruction": "Add one bounded exact-pixel edit.",
  "observation": {
    "stage": "semantic_details",
    "revision": 2
  }
}
```

P5-A0 deliberately leaves the contents of `observation` provider-neutral and JSON-compatible. **P5-A1** owns the compact-observation contract and will decide which deterministic facts, recent revision context, and bounded visual evidence should be exposed by default.

The A0 validator rejects non-JSON objects and non-finite numeric values so SDK response/message objects cannot accidentally leak into the core contract.

## Proposal v1

`tracepixel.agent-provider-proposal.v1` has one of two bounded candidate kinds:

```text
pixel_program -> existing tracepixel.pixel-program.v1 validator
stage_plan    -> existing tracepixel.stage-plan.v1 validator + external ArtIntent context
```

Example:

```json
{
  "schema": "tracepixel.agent-provider-proposal.v1",
  "kind": "pixel_program",
  "payload": {
    "schema": "tracepixel.pixel-program.v1",
    "canvas": {"width": 2, "height": 2},
    "operations": [
      {
        "op": "set_pixels",
        "pixels": [[1, 1, 10, 20, 30, 255]]
      }
    ]
  }
}
```

The proposal JSON Schema freezes only the outer discriminated envelope. Payload semantics are not duplicated: runtime validation delegates to the already-versioned P2/P3 validators that own PixelProgram and StagePlan correctness.

No A0 function executes a PixelProgram, mutates a `Canvas`, runs QA, or normalizes/deep-copies provider output.

## Python seam

`tracepixel.agent.AgentProvider` is a structural `Protocol`:

```python
class AgentProvider(Protocol):
    def propose(
        self,
        request: AgentProviderRequestV1,
        /,
    ) -> AgentProviderProposalV1: ...
```

External adapters may use any vendor SDK internally, but they must translate SDK-specific messages/responses into this plain provider-neutral boundary before returning to TracePixel. API keys, provider/model identity, HTTP clients, retries, rate-limit state, conversation objects, and network exceptions stay outside the A0 contract.

A deterministic fake object implementing the same single method is sufficient for tests; no provider dependency or network access is required.

## Stable rejection surface

A0 envelope failures raise `AgentProviderContractError` with stable `code`, `path`, and `message` fields. Invalid candidate payloads are rebased under `$.payload` while preserving the existing validator's code in the message.

StagePlan proposals require the caller to supply the authoritative ArtIntent validation context separately. This prevents a provider proposal from smuggling a second competing intent authority into the proposal envelope.

## Deliberate deferrals

A0 does **not** choose or define:

- compact observation contents/history retention — P5-A1,
- iteration, operation, or finish/revise orchestration — P5-A2,
- token/cost/wall-time telemetry — P5-A3,
- recorded provider fixtures — P5-A4,
- a real provider/model/network adapter — P5-A5 / owner gate G3,
- VLM correctness or perceptual scoring — separate owner gate G4.

Because A0 introduces no real provider/model or VLM judge, it does not cross G3 or G4.
