## Implementation

- [x] Preserve existing continuity repairs and terminal append ownership/fences.
- [x] Port shared usage rejection recognition and route/health/refresh predicates.
- [x] Add sustained-failure writer-slot probe and readiness integration.
- [x] Reconcile agent/full-resend recovery regressions while preserving all projectable context.
- [x] Repair confirmed lease cleanup through the actual iterator wrapper chain.

## Verification and rollout

- [x] Verify writer-slot release with real SQLite and concurrent background writes.
- [x] Run quota/context/settlement regressions and relevant static/spec gates.
- [x] Exercise official upstream/fork shared state and document any compatibility limits.
- [x] Sync verified requirements, archive verified work, and build fingerprinted release.
- [x] Stage remote runtime, perform ordinary service restart, and verify installed build and runtime health.
