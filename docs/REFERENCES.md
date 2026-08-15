# Reference Projects and Research

Observed: 2026-08-15. These are references for architecture and benchmark design, not code dependencies or automatic license compatibility claims.

## Direct pixel-agent references

### Texel Studio

- Repository: https://github.com/EYamanS/texel-studio
- Relevant ideas: Agent-controlled per-pixel/geometric tools, `view_canvas` feedback, palette management, item/block modes, autotile generation, provider-neutral-ish model selection, history/streaming.
- TracePixel question: can an explicit versioned Pixel IR, staged authority and preregistered Agent Complexity Budget improve reliability/efficiency over a broad tool loop?
- Do not copy source without separately reviewing its current license terms.

### pixel-mcp / Aseprite MCP (willibrandon)

- Repository: https://github.com/willibrandon/pixel-mcp
- Relevant ideas: Aseprite-backed canvas/layers/frames, batch pixel primitives, palette-aware drawing, dithering/shading, reference analysis, quantization and export.
- TracePixel question: which operations genuinely reduce Agent complexity, and which editor concepts are unnecessary for small standalone assets?

### aseprite-mcp (ayigityol)

- Repository: https://github.com/ayigityol/aseprite-mcp
- Relevant idea: a relatively broad Aseprite tool surface for AI assistants.
- TracePixel use: tool-count/discovery complexity reference; do not assume more exposed tools improve success.

### Other Aseprite MCP implementations

Multiple independent Aseprite MCP projects exist. Treat them as an ecosystem/reference family rather than one canonical baseline. A scored baseline must pin one exact repository/version and document Aseprite availability/licensing separately.

## Agent/canvas architecture references

### tldraw agent-template

- Repository: https://github.com/tldraw/agent-template
- Relevant ideas: Agent decisions use both structured canvas state and screenshots, plus lints and interaction history.
- TracePixel adaptation: provide compact structural canvas/IR facts alongside bounded visual previews instead of relying on screenshots alone.

## Generative sprite research references

### Sprite Sheet Diffusion: Generate Game Character for Animation

- Paper: https://arxiv.org/abs/2412.03685
- Relevant idea: diffusion-based character sprite-sheet generation addresses a different, higher-complexity identity/animation problem.
- TracePixel use: later comparison/promotion reference; not an initial icon/prop baseline unless a reproducible implementation is available.

### Generating Pixel Art Character Sprites using GANs

- Paper: https://arxiv.org/abs/2208.06413
- Relevant idea: conditional GAN generation of character poses from source sprites.
- TracePixel use: evidence that humanoid/multi-pose consistency is a distinct problem class and should have a later promotion gate.

### Show, Don't Tell / ProVisE + SpatialGen-Bench

- Paper: https://arxiv.org/abs/2607.21072
- Relevant idea: protocol-constrained visual outputs can be parsed into structured predictions and compared with task metrics.
- TracePixel use: benchmark-design reference for separating visual expression from machine-parseable evaluation, not a direct pixel-art baseline.

## Benchmark/reference policy

Before a reference becomes a scored baseline:

1. pin exact repository commit/release and tool/editor version,
2. record license and execution requirements,
3. document whether the run is direct, adapted or reimplemented,
4. match task information and budgets as closely as possible,
5. preserve raw outputs and failures,
6. label qualitative-only references honestly when matched execution is not feasible.
