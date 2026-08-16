# B0-S0 blind owner review

The provider-backed B0 cohort is complete and retained before this review begins. The final B0-S0 step is the preregistered **single repository-owner perceptual review**. It is not a VLM evaluation and it does not alter deterministic correctness.

## Frozen review contract

The owner reviews every completed artifact without method names in the existing per-task SHA-256 order. Each artifact receives an integer 1-5 score for:

- recognizability,
- readability at native 1x,
- style coherence.

The owner may also mark `human_rejection`. No pixel edits, output repair, method-specific hinting, reruns, or rating omissions are allowed.

## Local review surface

After updating the checkout to the commit that contains this tool, run:

```powershell
py -3.13 -m evidence.b0_s0.review
```

The command first validates the retained 28-attempt cohort, every artifact byte count/SHA-256 recorded by the attempt manifests, the 28-entry blind package, exact preview-byte copies, the frozen dimensions, and blind order. It then starts a **loopback-only** HTTP server on `127.0.0.1` and opens the browser.

Retained B0 result/review files are marked `-text` in `.gitattributes` because their exact committed bytes are SHA-256-addressed. This prevents Windows `core.autocrlf` from rewriting JSON line endings on new checkouts. A Windows checkout created before that attribute existed should update `main` and explicitly refresh only the retained evidence paths once before review:

```powershell
git checkout -- evidence/b0/results evidence/b0/review
```

This refreshes the working-tree copies from the unchanged committed evidence; it does not rerun or mutate the frozen cohort.

For each blind artifact the page shows:

- the exact visible task text,
- the authoritative 16x16 `final.png` at native 1x,
- the method-neutral 8x inspection preview,
- three 1-5 rating controls,
- the optional human-rejection checkbox.

The browser receives review IDs only. Method identities are resolved only server-side after the sealed rating record has been written.

## Sealing and immutability

Selecting **Seal owner review** requires all three ratings for all 28 artifacts. The tool writes:

- `evidence/b0/review/<freeze>/owner-review.json`
- `evidence/b0/review/<freeze>/owner-review-summary.json`

`owner-review.json` is bound to the exact blind `manifest.json` SHA-256 and intentionally contains no `method_id`. It is created with exclusive-create semantics, so the normal tool refuses to overwrite a sealed review. The derived summary unblinds the already-sealed review only for per-method perceptual aggregation; it cannot change the ratings.

If the process stops before sealing, no owner review record is created and the review may be restarted. If `owner-review.json` already exists and validates, the tool does not reopen the rating surface.

## Provider-free validation

Portable CI may validate already-retained evidence without performing any provider or human action:

```bash
python -m evidence.b0_s0.review --validate-package-only
```

Before owner review is recorded this reports `owner_review: absent`. After the sealed files are committed it also validates that the summary is exactly derived from the blind rating record.

## Completion boundary

B0-S0 advances to B0-P0 only after the sealed owner review files are committed and validated. Human scores remain a separate perceptual layer and never override the already-retained deterministic structural/completion/complexity evidence. G4 VLM judging remains disabled.
