# B0-S0 Korean-first mobile owner review

B0-S0 can be reviewed entirely from a phone without exposing the scored method identity and without connecting the phone to the owner-local benchmark machine.

## Trusted mobile path

The `B0 Owner Blind Review Artifact` workflow runs only from trusted `main` and performs no provider or VLM calls. It validates the already-retained B0 cohort through the existing owner-review contract, then builds one offline artifact containing:

- `index.ko.html` — default Korean review page,
- `index.html` — English companion page,
- `manifest.json` — package provenance and frozen review binding.

All native and 8x PNGs are embedded as `data:` URIs, so the HTML needs no server or network after extraction.

## Phone instructions

1. Open **GitHub → TracePixel → Actions**.
2. Open the latest successful **B0 Owner Blind Review Artifact** run on `main`.
3. Download `tracepixel-b0-owner-review-<40-hex-main-sha>`.
4. Extract the ZIP on the phone.
5. Open `index.ko.html` in a browser.
6. Rate all 28 blind artifacts on the frozen 1–5 dimensions:
   - **인식 가능성** (`recognizability`),
   - **원본 1배 크기 가독성** (`readability_at_native_1x`),
   - **스타일 일관성** (`style_coherence`).
7. Mark **사람 기준 탈락** only when the artifact should receive the preregistered `human_rejection` flag.
8. When progress reaches `28/28`, use **평가 JSON 저장** or **평가 JSON 공유** to produce `owner-review.json`.
9. Upload that JSON back to the project/chat for validation and repository retention.

The Korean task description is a convenience translation. The exact canonical English task text is retained under **원문 조건** on every task section so translation cannot silently redefine the benchmark.

## Blindness and integrity

The static page and exported `owner-review.json` contain review IDs, task IDs, trial indices, blind order, the frozen manifest SHA-256, and human ratings. They do **not** contain `method_id` or either scored method name.

The page cannot alter retained rasters, deterministic QA, complexity telemetry, provider responses, or benchmark schedule. The exported JSON becomes authoritative owner-review evidence only after it is validated against the committed blind package and retained in the repository.

## Mobile behavior

The page is responsive and Korean-first. It attempts to retain in-progress selections in browser `localStorage` using a key bound to the frozen review-manifest SHA. Because Android local-file viewers differ, progress persistence is best-effort; keep the page open until export when possible.

Three export paths are provided:

- **평가 JSON 저장** — downloads `owner-review.json`,
- **평가 JSON 공유** — uses the phone's Web Share API when file sharing is supported,
- **JSON 복사** — copies the exact JSON text as a fallback.

No ratings can be exported until all 84 required scores (28 artifacts × 3 dimensions) are present.

## Completion boundary

Using the mobile package does not itself advance B0-S0. B0-S0 advances to B0-P0 only after the exported owner review is validated, retained, and the derived method-labelled perceptual summary is generated from the already-sealed blind ratings.
