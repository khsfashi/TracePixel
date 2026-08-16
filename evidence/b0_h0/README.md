# B0-H0 matched harness checkpoint

This directory contains the provider-free regression checkpoint for the frozen B0-v1 matched harness.

The authoritative B0-F0 freeze commit is `c4b31288867fd4c4cf5ea3664808bd6f47cca1db`. H0 does not modify the frozen tasks, methods, model/settings, budgets, scoring, retry/exclusion policy, or retention contract.

`python -m evidence.b0_h0.checkpoint` verifies that:

- the preregistration file still loads as the frozen B0 contract,
- the frozen task/method/trial product materializes exactly 28 primary attempts,
- attempt identities and blind-review keys are unique,
- provider-visible task packets contain only the frozen visible text/tier/identity and never the hidden structural constraints,
- the checkpoint itself performs zero provider invocations and starts zero scored attempts.

Unit tests additionally exercise failure retention, zero structural scoring for non-completion, exact frozen rule-set scoring, the one-time `void_infrastructure` rerun boundary, byte-artifact hashing, and immutable attempt paths.

Actual scored provider execution remains deferred. B0-B0 must implement the two frozen method adapters before B0-S0 can run the cohort.
