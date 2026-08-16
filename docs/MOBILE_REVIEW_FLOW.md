# P6-V5 Mobile Review Flow

P6-V5 proves the owner can review one trusted P6-V4 static-gallery artifact from a phone without a desktop editor, server, provider call, VLM judge or self-hosted preview runner.

The mobile path is presentation and human review only. It does not change raster authority, deterministic QA authority or Agent-complexity semantics.

## What must be identifiable

A successful phone review must let the owner identify all five P6 acceptance targets:

1. **Task / intent** — the asset class, canvas and authored ArtIntent.
2. **Final output** — the enlarged nearest-neighbor final preview.
3. **Stage progression** — the authored-stage contact sheet.
4. **Deterministic QA** — status and finding count from deterministic evidence.
5. **Agent complexity** — whether complexity evidence is present and the observational metrics composition.

The gallery also keeps the authority boundary visible so a phone screenshot or human impression cannot become canonical raster or QA truth.

## Trusted phone path

Use only the P6-V4 `Trusted Gallery Artifact` workflow on `main`.

1. Open the repository's **Actions** view and select the latest successful `Trusted Gallery Artifact` run for `main`.
2. Confirm the run source is the intended trusted `main` commit. The artifact suffix must match that exact 40-hex source SHA.
3. In the run's **Artifacts** section, download `tracepixel-static-gallery-<source-sha>`.
4. Extract the ZIP with the phone's normal files application.
5. Open the extracted `index.html` in a local phone browser.
6. Review the page from top to bottom. The summary badges appear first, followed by:
   - Final output
   - Deterministic QA + Agent metrics
   - Stage progression evidence
   - Task / intent
   - Authority boundary
7. Confirm that each of the five review targets above is identifiable without switching to a desktop/editor or contacting a server.

The artifact contains only `index.html` and `manifest.json`. The HTML has no JavaScript or remote assets, so after download/extraction the review itself does not require network-backed page resources.

## Security / provenance boundary

Treat the artifact as public review data.

- Do not put secrets, provider credentials, private prompts, internal assets or personal information in the gallery.
- Do not substitute an artifact produced from untrusted PR code. P6-V4 intentionally publishes only from trusted `main`.
- The artifact name/source SHA is provenance metadata, not a cryptographic attestation. Artifact attestation remains a separate future security decision.
- Opening the local page does not authorize code execution: the P6-V3 CSP remains restrictive and the page contains no script.
- P6-V5 does not invoke a provider or VLM and therefore does not cross unresolved G4.
- P6-V5 does not use the owner Windows runner and therefore does not cross unresolved G6.

## Machine-checkable review surface

Portable CI runs:

```bash
python -m evidence.p6_v5.checkpoint
```

This rebuilds the provider-free P6-V3 reference gallery and rejects regressions that remove the phone viewport, one of the five review sections/cues, the summary badges, the frozen scan order, or the no-script/no-network-resource baseline.

This automated check proves the **review surface contract**, not that a human actually used a phone.

## Owner proof record

P6-V5 completes only after one real owner phone review is recorded. The proof uses schema `tracepixel.mobile-review-proof.v1`:

```json
{
  "schema": "tracepixel.mobile-review-proof.v1",
  "repository": "khsfashi/TracePixel",
  "source_sha": "<40-hex trusted main SHA>",
  "workflow_run_id": 123456789,
  "artifact_id": 123456789,
  "artifact_name": "tracepixel-static-gallery-<same source SHA>",
  "device_class": "phone",
  "access_path": "github-actions-artifact-download",
  "observations": {
    "task_intent": true,
    "final_output": true,
    "stage_progression": true,
    "deterministic_qa": true,
    "agent_complexity": true
  },
  "perceptual_vlm_used": false,
  "self_hosted_runner_used": false
}
```

Validate a completed record with:

```bash
python -m evidence.p6_v5.checkpoint --proof path/to/review-proof.json
```

The proof records only whether the required information was identifiable. It does **not** encode an aesthetic approval score and must not be used as deterministic correctness evidence.

## Completion boundary

The implementation/checkpoint may merge while `current_child` remains `P6-V5`.

Advance to P6-V6 only after:

- the implementation CI is green,
- a trusted-main P6-V4 artifact exists for the chosen source SHA,
- the owner performs the phone flow above,
- the proof record validates with all five observations `true`.

P6-V6 is optional home-PC runner work and remains separately blocked by owner gate G6.
