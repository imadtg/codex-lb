# Beta.8 integration evidence

Base: published v1.25.0-beta.8 (`bb4db9d0`). Source of local behavior: `a23315e1`, based on beta.7. Live deployment is left unchanged while validating.

## Implementation decisions

- Keep upstream #2390/#2397 durable owner retirement, including its explicit client-anchor and file-owner restrictions.
- Replace local excluded-owner selector branch and result-type relocation with upstream #2381. Upstream carries a boolean reason through selection, avoiding our alternate error envelope.
- Keep upstream #2384 rejection classifier and request logging. Attach local bounded request-stage evidence without replacing the upstream rejection contract.
- Drop the local missing-proof fallback from `durable_full_resend_allows_account_neutral_replay`; upstream deliberate owner retirement now owns that decision. This does not assert all loss-of-proof incidents are solved.
- Retain fenced explicit quota handoff, validated plaintext host input and the client fingerprint across outgoing projection. Separate ordinary, historical-developer, namespace, prefix-agent and suffix-agent probes isolate each allowance.
- Remove the speculative sequenced prewarm/capacity extension and its arithmetic-only unit tests. Real Codex sends an incremental suffix after prewarm; the corrected process control preserves beta.8's explicit sequenced capacity refusal. This limitation is not a successful recovery.
- Restore the same-account fence on proof-preserving account rebind. Copying completion proof between accounts was not the failed-replacement fix.
- Keep the existing reversible alias-publication receipt until the provider's outcome is known. An explicit quota rejection before creation rolls back that provisional alias under the original epoch/account fences, with no concurrent pending request. Accepted or ambiguous replacement outcomes cannot use this rollback.
- A closed predecessor whose stale anchor was retired can use the existing account-neutral recovery lane only after its retained full-history proof succeeds. This avoids reopening an unanchored owner-pinned socket without operation admission.
- Preserve the provider's quota terminal when mandatory-owner retry selection returns `no_accounts` before replacement dispatch. Changed history still cannot move accounts; a selection failure must not masquerade as transport loss.

## Concrete failed-replacement example

A completes a tool turn. On the next full resend A rejects its stale response anchor;
B's recovery attempt rejects quota before response creation. Previously the client
turn alias stayed on B's lane without completion proof, stranding the identical
resend even after eligible C was imported. The process reproducer now observes
dispatch order A, A, B, C and exact projected history on C. Counterfactual providers
that accept B's response or disconnect ambiguously must never dispatch on C.

This uses beta.8's existing receipt rollback and recovery lanes. It adds a narrow
terminal lifecycle transition, not a new selector or a new persistent schema.

## Test method

The same probe script launches each checkout as a separate process with disposable HOME/data/database and synthetic accounts imported through the dashboard API. Requests and quota failures are delivered over public HTTP/WebSocket interfaces. No live data is copied or modified and no SQL writes manufacture replay proof. Provider mocks record dispatched accounts, body, anchor and turn-state presence; positive and negative controls check these wire results.

The old optional real-Codex integration test is retained as historical coverage but uses in-process application fixtures; it is not described as a public-process test. The metadata refresh background task can fetch public pricing metadata; synthetic inference traffic targets loopback only.

Durable evidence is under `../audit-artifacts/beta8-tests/`. Broad migration tests
used disposable disk databases. Process comparisons use disposable databases in
`/dev/shm/codex-lb-validation.tFbIa0` to avoid the small `/tmp` quota and loaded-disk
startup timeouts. Those tmpfs runs do not demonstrate power-loss durability.
See `test-evidence.md` for source provenance, test results and unproved boundaries.
The frontend was built with Bun 1.3.14. Automatic migrations remain enabled;
there are no local migration revisions. Live remains beta.7 `a23315e1`.
