# P6-V4 Trusted GitHub Artifact Publishing

P6-V4 publishes the existing deterministic P6-V3 static gallery through a deliberately narrow GitHub Actions boundary. It does not add a new raster, QA or perceptual authority.

## Trust boundary

The publication workflow is `.github/workflows/trusted-gallery-artifact.yml`.

It is intentionally owner-triggered only:

- trigger: `workflow_dispatch` only,
- accepted repository: `khsfashi/TracePixel`,
- accepted ref: `refs/heads/main`,
- runner: GitHub-hosted `ubuntu-latest`,
- repository permission: `contents: read`,
- checkout: exact triggering `${{ github.sha }}` with persisted credentials disabled,
- provider/model call: none,
- secret reference: none,
- self-hosted runner: none,
- artifact retention: 14 days.

A public pull request cannot invoke this publication workflow. Normal pull-request CI remains the separate provider-free `.github/workflows/ci.yml` path.

The job-level repository/ref check is deliberate defense in depth. `workflow_dispatch` is already a trusted manual entry point on the default branch, but the job still refuses any ref other than `main`.

## Published payload

The workflow installs TracePixel and runs:

```bash
python -m evidence.p6_v3.checkpoint --output artifacts/p6-v4-static-gallery
```

That rebuilds the same provider-free P6-V3 reference gallery already checked by portable CI. The uploaded directory contains only:

```text
index.html
manifest.json
```

The artifact name includes the exact triggering source commit:

```text
tracepixel-static-gallery-<40-hex-source-sha>
```

The gallery remains self-contained: no JavaScript, no remote image/font/style dependency, restrictive CSP, and embedded PNG/SVG data URIs. The artifact itself should therefore be treated as public review data, not as a place for credentials, private prompts, internal assets or personal information.

## Why PR artifacts are not publication authority

P6-V4 deliberately does not upload a gallery from `pull_request` or `pull_request_target`.

A pull request can modify the gallery generator, CSP, workflow code or presentation content. Therefore an artifact produced from untrusted PR code must never be promoted implicitly into an owner-trusted review result. The trusted publication path instead executes the exact `main` commit recorded in `github.sha`.

This boundary is about provenance and execution trust, not merely about whether the generated HTML currently contains scripts.

## Regression checkpoint

Portable CI runs:

```bash
python -m evidence.p6_v4.checkpoint
```

The checkpoint verifies the committed workflow still requires the frozen V4 policy and rebuilds the deterministic P6-V3 payload. It fails if the publication workflow gains a public-PR trigger, self-hosted runner, secret reference, write permission, unapproved action surface, non-main dispatch path, or longer/different artifact retention without an explicit policy change.

This is a repository regression guard, not a cryptographic attestation mechanism.

## Attestation

GitHub artifact attestations are intentionally deferred. Adding attestation would require widening workflow permissions (for example provenance/identity permissions), so it should be introduced only as a separate, explicit security decision rather than silently expanding this minimal V4 workflow.

## Completion boundary

The code/config portion of P6-V4 is complete only after portable CI is green. The child itself should advance to P6-V5 only after the trusted workflow has also been executed from `main` and GitHub confirms that the expected static-gallery artifact was uploaded successfully.

P6-V5 will document and prove the actual phone review path. P6-V6 remains separately gated by G6 and does not inherit authorization from this GitHub-hosted workflow.
