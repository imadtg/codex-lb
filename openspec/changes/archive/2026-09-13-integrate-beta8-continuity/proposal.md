# Integrate beta.8 continuity fixes

## Why
Adopt published v1.25.0-beta.8 and retain only local continuity behavior that public-process evidence shows remains missing. Preserve historical outside-in regression scenarios independently of implementation.

## What Changes
- Establish an unmodified beta.8 baseline using disposable databases and loopback providers.
- Prefer upstream owner retirement, affinity selection, and replay diagnostics where they meet the behavioral contract.
- Port only demonstrated missing fixes, retaining high-level regression evidence and documenting safety-policy differences.

## Impact
Proxy continuity and regression tests. No live database experiments. Deployment follows candidate validation.
