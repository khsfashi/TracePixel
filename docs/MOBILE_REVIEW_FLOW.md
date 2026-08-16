# P6-V5 Mobile Review Flow

P6-V5 proves the owner can review one trusted GitHub Actions artifact from a phone without a desktop editor, server, provider call, VLM judge or self-hosted preview runner.

The mobile layer is presentation and human review only. It does not change raster authority, deterministic QA authority, stage provenance, or Agent-complexity semantics.

## Bilingual static package

The trusted artifact now layers `tracepixel.mobile-review-package.v1` over the verified P6-V3 gallery and contains exactly:

```text
index.html
index.ko.html
manifest.json
```

`index.html` is English and `index.ko.html` is Korean. Each page contains a relative link to its companion page. There is no JavaScript language runtime and no external localization dependency. If an Android `content://` viewer does not resolve sibling relative links, open the other HTML file directly from the extracted artifact folder; both files are complete standalone review pages.

The Korean page translates the review chrome and explanations. Canonical stage identifiers, source JSON keys and embedded source-evidence compositions may remain in English so localization cannot silently rewrite evidence semantics.

## What must be identifiable

A successful phone review must let the owner identify all five P6 acceptance targets:

1. **Task / intent** — the asset class, canvas and authored ArtIntent.
2. **Final output** — the enlarged nearest-neighbor final preview.
3. **Stage progression** — either exact linked stage provenance or an explicitly labeled separate stage-workflow reference.
4. **Deterministic QA** — status and finding count from deterministic evidence.
5. **Agent complexity** — whether complexity evidence is present and the observational metrics composition.

The gallery also keeps the authority boundary visible so a phone screenshot or human impression cannot become canonical raster or QA truth.

## Stage provenance states

P6-V5 must not imply that unrelated stage images produced a final output.

- `bundle-stage-artifacts`: every contact-sheet frame matches a `stage-image` record from the final preview bundle by exact source path and SHA-256. The page labels this as linked provenance.
- `separate-reference`: the final bundle contains no stage-image records. The page displays a prominent warning that the contact sheet is separate committed workflow evidence and is **not** the intermediate history of the final image.

The frozen P5-A5 final-output reference is intentionally `separate-reference`: it came from one final PixelProgram proposal and did not run the P3 staged pipeline. Visual differences between that final potion and the P3 stage-workflow reference are therefore expected, not hidden.

## Mobile stage-sheet readability

The deterministic P6-V1 SVG still embeds source PNG bytes at natural dimensions with no raster resampling. The presentation cells now reserve a phone-readable minimum width, place the stage index and stage label on separate lines, and keep the six-stage three-column reference sheet within a roughly phone-sized natural viewBox. This fixes label overflow without changing source pixels.

## Trusted phone path

Use only the `Trusted Static Gallery Artifact` workflow on `main`.

1. Open the repository's **Actions** view and select the latest successful trusted gallery run for `main`.
2. Confirm the run source is the intended trusted `main` commit. The artifact suffix must match that exact 40-hex source SHA.
3. Download `tracepixel-static-gallery-<source-sha>`.
4. Extract the ZIP with the phone's normal files application.
5. Open `index.html` for English or `index.ko.html` for Korean.
6. Review from top to bottom: summary badges, final output, deterministic QA + Agent metrics, stage provenance/reference, task/intent, authority boundary.
7. Confirm all five required review targets are identifiable without a desktop/editor or network-backed page resource.

## Security / provenance boundary

Treat the artifact as public review data.

- Do not put secrets, provider credentials, private prompts, internal assets or personal information in the gallery.
- Do not substitute an artifact produced from untrusted PR code. Publication remains trusted-main only.
- Artifact name/source SHA is provenance metadata, not a cryptographic attestation.
- The localized pages retain the restrictive V3 CSP, contain no script, and load no remote assets.
- P6-V5 does not invoke a provider or VLM and therefore does not cross unresolved G4.
- P6-V5 does not use the owner Windows runner and therefore does not cross unresolved G6.

## Machine-checkable review surface

Portable CI runs:

```bash
python -m evidence.p6_v5.checkpoint
```

The checkpoint rebuilds the provider-free V3 reference, builds both static language pages, and rejects regressions in:

- phone viewport metadata,
- five-section scan order,
- summary badges,
- English/Korean companion navigation,
- prominent stage provenance state,
- script/external-network independence.

To materialize the exact payload used by trusted publication:

```bash
python -m evidence.p6_v5.checkpoint --output out/p6-v5-mobile-review
```

This automated check proves the **review surface contract**, not that a human actually used a phone.

## Owner proof record

P6-V5 completes only after one real owner phone review is recorded. The current proof schema is `tracepixel.mobile-review-proof.v2` and records which static language page was actually reviewed:

```json
{
  "schema": "tracepixel.mobile-review-proof.v2",
  "repository": "khsfashi/TracePixel",
  "source_sha": "<40-hex trusted main SHA>",
  "workflow_run_id": 123456789,
  "artifact_id": 123456789,
  "artifact_name": "tracepixel-static-gallery-<same source SHA>",
  "language": "ko",
  "review_page": "index.ko.html",
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

Advance to P6-V6 only after the corrected bilingual package is green on `main`, a trusted-main artifact exists for that source SHA, the owner performs the phone flow on one recorded language page, and the proof validates with all five observations `true`.

P6-V6 remains optional home-PC runner work and is separately blocked by owner gate G6.
