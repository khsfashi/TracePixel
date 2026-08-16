# P6-V4 Trusted GitHub Artifact Publishing

P6-V4 publishes deterministic review evidence through a deliberately narrow GitHub Actions boundary. After the P6-V5 mobile-review refinement, the same trusted workflow packages the verified P6-V3 gallery into a bilingual static phone-review payload; it still does not add a new raster, QA or perceptual authority.

## Trust boundary

The publication workflow is `.github/workflows/trusted-gallery-artifact.yml`.

It accepts only trusted `main` execution:

- triggers: push to `main` or explicit `workflow_dispatch`,
- repository: `khsfashi/TracePixel`,
- ref: `refs/heads/main`,
- runner: GitHub-hosted `ubuntu-latest`,
- repository permission: `contents: read`,
- checkout: exact triggering `${{ github.sha }}` with persisted credentials disabled,
- provider/model call: none,
- secret reference: none,
- self-hosted runner: none,
- artifact retention: 14 days.

A public pull request cannot invoke this publication workflow. Normal pull-request CI remains separate provider-free CI.

## Published payload

The trusted job runs:

```bash
python -m evidence.p6_v5.checkpoint --output artifacts/p6-v4-static-gallery
```

That command rebuilds the provider-free P6-V3 source gallery, applies the deterministic P6-V5 mobile review package, validates both language pages, and writes exactly:

```text
index.html
index.ko.html
manifest.json
```

`index.html` is English and `index.ko.html` is Korean. Both remain script-free and remote-resource-free. The package manifest records both page digests plus the exact P6-V3 source-gallery digest and stage-linkage state.

The artifact name still includes the exact triggering source commit:

```text
tracepixel-static-gallery-<40-hex-source-sha>
```

Treat the artifact as public review data, not as a place for credentials, private prompts, internal assets or personal information.

## Why PR artifacts are not publication authority

A pull request can modify the gallery generator, localization layer, CSP, workflow code or presentation content. Therefore an artifact produced from untrusted PR code must never be promoted implicitly into an owner-trusted review result. The trusted path executes the exact `main` commit recorded in `github.sha`.

## Regression checkpoint

Portable CI runs:

```bash
python -m evidence.p6_v4.checkpoint
```

The checkpoint rejects public-PR triggers, non-main publication, self-hosted runners, secret references, write permissions, unapproved action surfaces or retention drift. It also requires the publication payload to contain exactly the English page, Korean page and manifest produced by the deterministic P6-V5 package.

This is a repository regression guard, not a cryptographic attestation mechanism. Artifact attestations remain deferred because they would widen workflow permissions.

## Authority boundary

Localization, phone layout and stage-provenance notices are presentation-only. Authoritative raster bytes and deterministic QA remain their existing source evidence. `separate-reference` is explicitly disclosed rather than presented as final-output provenance, while `bundle-stage-artifacts` is accepted only after the existing exact path/SHA-256 linkage check succeeds. G4 and G6 remain untouched.
