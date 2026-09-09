# Implemented and verified work
- [x] Revisit original T3 recovery thread and recurrence evidence, read-only.
- [x] Inventory upstream fixes and CLIProxyAPI recovery precedents.
- [x] Implement privacy-preserving classifier instrumentation.
- [x] Fix normal Codex controls, namespaces and sent-history fingerprint compatibility.
- [x] Distinguish attempt-excluded hard owners from recoverable saturation.
- [x] Integrate #2121 exact complete-tool-manifest plus fresh-input recovery; remove strict xfail.
- [x] Integrate #2069 soft-owner quota recovery and #2111 owner publication before delivery.
- [x] Preserve replay proof during same-owner, epoch/anchor-fenced poison abandonment.
- [x] Add validated unanchored portable-history recovery for legacy erased proof.
- [x] Exercise the real Codex 0.152 binary against synthetic 1012 after tool completion.
- [x] Exercise unmodified Codex through the real codex-lb route and selector on HTTP and WebSocket upstreams, preserving tool results across account replacement.
- [x] Fix namespace parameter-schema false positives and validate web-search boolean controls.
- [x] Preserve replay evidence through both response-anchor retirement paths and decode retained manifests without a live anchor.
- [x] Prepare unpublished upstream report, provenance and failure map.

# Final validation
See FINAL_VALIDATION.md for completed runs and their boundaries.

# Outside the verified candidate
- Out of scope: T3 adapter implementation and stale adapter lifecycle; all exploratory T3 changes reverted. Real Codex compatibility is exercised within codex-lb tests.
- [ ] Supported portable reconstruction/export for encrypted compaction and account-owned files.
- [ ] Separate atomic commits/upstream submissions and upstream CI/review; not authorized or performed.
- [ ] Production deployment and user verification; live instance remains read-only.

The change stays active, not archived: opaque-context reconstruction is unresolved; T3 lifecycle work is outside the authorized codex-lb scope.

# Observability and upstream reassessment follow-up
- [x] Emit versioned, content-free shared classifier outcomes and durable proof-gate reasons.
- [x] Verify log correlation, redaction and route behavior with regressions; retain the separately failing live-quota reproduction.
- [x] Inspect current main and current related discussions in codex-lb and CLIProxyAPI; record dated SHAs and distinguish evidence from inference.
- [x] Document diagnostic coverage and remaining blind spots; prepare a scoped upstream submission recommendation.

- [x] Complete durable-operation-fenced live-quota handoff; both real-Codex transports now pass without a third client request. See LIVE_QUOTA_HANDOFF.md.
- [x] Attribute AdmissionLease warnings to incomplete unit-test cleanup; fix teardown and verify with a test-only allocation probe.
