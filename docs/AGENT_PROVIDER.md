# Provider-neutral Agent interface

P5-A0 introduces the replaceable provider boundary. P5-A1 narrows each request to one versioned compact observation, and P5-A2 now supplies bounded deterministic PixelProgram orchestration without selecting a provider, model, SDK, retry policy, network transport, or cost envelope.

The authority direction remains:

```text
provider-neutral request + compact observation
  -> provider proposal
  -> existing PixelProgram / StagePlan validation
  -> bounded deterministic orchestration where applicable
  -> deterministic raster + QA authority
```

A provider proposal is candidate data only. It never becomes canonical raster or Pixel IR truth merely because a model or adapter returned it.

## Request v1

`tracepixel.agent-provider-request.v1` remains the closed outer envelope:

```json
{
  "schema": "tracepixel.agent-provider-request.v1",
  "instruction": "Add one bounded exact-pixel edit.",
  "observation": {
    "schema": "tracepixel.agent-observation.v1",
    "intent": {},
    "current": {},
    "qa": {},
    "preview": null,
    "recent": []
  }
}
```

P5-A1 makes `observation` reference `tracepixel.agent-observation.v1`. Generic arbitrary JSON observations accepted during the A0 seam-freezing step are no longer valid provider requests.

The compact contract contains validated ArtIntent, current stage/revision, typed Q5 findings, an optional size-bounded PNG preview, and at most four recent revision summaries. The normal builder accepts no Canvas and no transcript. See `docs/AGENT_OBSERVATION.md`.

The request validator still rejects non-JSON SDK objects and non-finite numeric values before applying the compact-observation validator.

## Proposal v1

`tracepixel.agent-provider-proposal.v1` has one of two bounded candidate kinds:

```text
pixel_program -> existing tracepixel.pixel-program.v1 validator
stage_plan    -> existing tracepixel.stage-plan.v1 validator + external ArtIntent context
```

The proposal JSON Schema freezes only the outer discriminated envelope. Payload semantics are not duplicated: runtime validation delegates to the already-versioned P2/P3 validators that own PixelProgram and StagePlan correctness.

A0/A1 validation functions do not execute a PixelProgram, mutate a `Canvas`, run raster analyzers, select a model, perform network I/O, or turn provider output into authority. P5-A2 adds a separate orchestration surface for validated `pixel_program` candidates; see `docs/AGENT_LOOP.md`.

## Python seam

`tracepixel.agent.AgentProvider` remains a structural `Protocol`:

```python
class AgentProvider(Protocol):
    def propose(
        self,
        request: AgentProviderRequestV1,
        /,
    ) -> AgentProviderProposalV1: ...
```

External adapters may use any vendor SDK internally, but they must translate SDK-specific messages/responses into this plain provider-neutral boundary. API keys, provider/model identity, HTTP clients, retries, rate-limit state, conversation objects, and network exceptions stay outside the core contract.

A deterministic fake object implementing the same method remains sufficient for tests; no provider dependency or network access is required.

## P5-A2 bounded edit orchestration

`run_bounded_edit_loop(...)` consumes the same provider request/proposal seam but deliberately accepts only `pixel_program` proposals against an existing authoritative Canvas. `stage_plan` remains a valid A0 provider candidate kind and is not reinterpreted as an incremental Canvas edit.

A2 requires a closed explicit iteration/tool/operation/pixel-edit budget, validates every candidate before mutation, runs caller-supplied deterministic QA after accepted edits, and finishes only when the selected typed Q5 findings are empty. Optional bounded PNG observation is generated only while another provider decision is actually required.

The A2 control result is intentionally not Agent complexity telemetry. Token/cost/wall-time and aggregate complexity evidence remain P5-A3.

## Stable rejection surface

Outer envelope failures raise `AgentProviderContractError`. Compact observation failures are rebased under `$.observation` as `invalid_observation`; invalid candidate payloads are rebased under `$.payload` while preserving the underlying deterministic validator code in the message.

StagePlan proposals still require authoritative ArtIntent validation context separately. The compact observation does not become a second validation authority for a proposed StagePlan.

A2 configuration/candidate failures raise `AgentLoopContractError`; budget exhaustion is a normal `AgentLoopResult.status` and does not apply an over-budget candidate.

## Deliberate deferrals

A0-A2 do **not** choose or define:

- token/cost/wall-time telemetry — P5-A3,
- the dedicated recorded provider orchestration checkpoint — P5-A4,
- a real provider/model/network adapter — P5-A5 / owner gate G3,
- VLM correctness or perceptual scoring — separate owner gate G4.

Because A2 adds no live provider/model or perceptual judge, it does not cross G3 or G4.
