# P5-A4 recorded/fake-provider CI

This checkpoint proves the P5 provider-neutral orchestration path in portable CI without selecting or calling a real model provider.

## Fixture

`recording.json` is a small synthetic provider recording with a closed `tracepixel.p5-a4-recorded-provider.v1` envelope. It contains exactly two provider-neutral PixelProgram proposals plus provider-neutral usage samples:

1. a valid transparent-black write that leaves deterministic QA unresolved,
2. a valid opaque write that resolves the `structural.non_empty` finding.

The sequence therefore exercises the revise path rather than only a one-shot finish.

## Checkpoint

`python -m evidence.p5_a4.checkpoint`:

- loads and validates the closed recording envelope,
- replays it through `run_bounded_edit_loop_with_telemetry(...)`,
- requires both recorded calls to be consumed,
- checks exact final authoritative RGBA bytes,
- checks the final bounded observation and revision count,
- checks deterministic complexity counters and recorded token/cost aggregation,
- excludes `wall_time_ns` from deterministic equality because timing is observational evidence,
- runs the whole replay twice and requires all non-timing evidence to be identical.

The normal unit-test suite also checks the checkpoint and rejects malformed recording fields/usage values.

## Authority and scope

The recording is development evidence only. It is not a scored benchmark cohort, a quality claim, or a real provider transcript. Provider output remains candidate data; PixelProgram validation, raster mutation, deterministic QA, and loop budgets remain authoritative exactly as in P5-A0 through P5-A3.

This checkpoint adds no provider SDK, API key, network request, secret, VLM/perceptual judge, GPU requirement, or self-hosted runner. It deliberately does not cross owner gate G3. The first real provider/model remains P5-A5 scope.
