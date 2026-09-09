# Live quota handoff follow-up — September 9, 2026

The two previously failing real-Codex quota reproductions now pass without a third client request. This supersedes the live-quota blocker recorded in OBSERVABILITY.md and FINAL_VALIDATION.md; those historical failures remain evidence of what the earlier candidate missed. It does not claim arbitrary opaque or account-owned contexts can migrate, or that production has been tested.

## Changes and invariants

The bridge quota handler previously stripped a proxy anchor and tried an in-place reconnect. Its durable operation still belonged to A, while selection excluded A. Explicit pre-created quota rejection now reaches the existing outer operation-fenced recovery path. It resets the rejected operation's spool under the original owner fence, retires the old session, preserves the operation identity, and re-registers it under the replacement session before dispatch. The existing repository transaction and predecessor-owner rules continue to prevent stealing a live operation. No database schema or operation-fence weakening was introduced.

The new quota admission helper rejects registered-response/visible-output cases, prior replay, missing operation registration or fence, other pending requests, explicit turn-state ownership, account-bound files and unproven portable history. The attempt is bounded to one server-side replay. Transport timeouts, incomplete streams and generic overload do not qualify as explicit quota rejection. Existing model-capacity handling remains ahead of quota handling.

Direct HTTP had a separate gap: the unanchored-history projection required a completed assistant message, although Codex can send a complete tool-call/result exchange without one. The new plaintext-only normalization removes response-item IDs and nothing else. It requires user input and validates the whole resulting payload, including paired tool calls/results. It rejects anchors, conversations, files, opaque reasoning/compaction and unknown items. This is confined to the existing soft-owner, pre-visible quota-rejection branch; it is not evidence for removing an anchored continuation's ownership.

## Diagnostics

`continuity_decision stage=quota_handoff` now records `fenced_replay_eligible`, `plaintext_replay_eligible`, or the actual admission gate: `operation_unregistered`, `output_started`, `already_replayed`, `operation_fence_missing`, `other_requests_pending`, `explicit_turn_state`, `file_bound`, `portable_context_unproven`. Existing proof-classifier events explain the last category. The exporter allowlist includes these values. The existing bridge event `quota_recover_fresh_resend` records entry into the recovery path; existing operation and terminal logs still provide the subsequent lifecycle evidence.

These events are bounded observations through the existing logger, not a guaranteed durable audit journal. Absence of a record is not proof of success. Nested classifier branches and all selection filters are not exhaustively traced.

## Reproduction and verification

The real-client test now parametrizes both pause and quota by default when the versioned binary is supplied; the formerly failing quota cases are no longer hidden behind a separate mode. `CODEX_LB_TEST_LOSS_MODE` is no longer used.

```sh
CODEX_LB_TEST_CODEX_BINARY=/home/imad/.local/share/mise/installs/codex/0.152.0/bin/codex \
uv run pytest -q tests/integration/test_codex_binary_continuity.py --timeout=65 --tb=short
```

Final real-client run: **4 passed, 48.58s**. Two client requests in every case, preserved tool output, and A-to-B dispatch. HTTP has three provider dispatches in quota mode (initial success on A, rejected follow-up on A, recovered follow-up on B), while the reused WebSocket needs two socket connections. The assertion distinguishes dispatches from connections; it does not allow an extra client request.

Additional verification:

- **294 unit cases passed**, covering replay validation, plaintext normalization, quota admission and redacted export.
- **8 route boundary cases passed**, then **2 added cases passed** for rate-limit rejection and an omitted parallel tool result. Tests assert operation identity preservation and final ledger ownership, rejection of changed/incomplete history, missing operation fence, failed spool reset, known explicit turn-state, prior visible output and bounded replacement rejection.
- **2 keyed route cases passed**: successful replacement and replacement quota rejection. No reservation remains reserved. Usage equals exactly completed responses (28 tokens after success; 2 when replacement rejects).
- **53 HTTP transient-retry cases passed**, including both status and SSE quota envelopes and incomplete tool-history refusal.
- **21 existing stale-anchor recovery cases passed**, including fencing, spool failures, prior replay and circuit-generation restrictions.
- **325 focused bridge/helper cases passed** under an allocation probe; counts overlap earlier runs.

### Admission warning attribution

A temporary test-only allocation probe identified five leaking parametrized cases in four unit-test functions: tests successfully staged a retry, asserted its new admission lease was held, and ended without simulating completion or cleanup. The production allocation stack was the intended retry admission acquisition. Test teardown now calls the existing response-create ownership cleanup and checks gate/admission release. All **6 parametrized cases passed**, with no new unreleased-admission origin recorded by the probe. No production suppression of the warning was added. This explains the observed warning, not every possible resource leak.

## Scope

Live service, accounts, T3 sessions and production data were not changed. Tests use loopback synthetic providers and disposable databases; the real Codex 0.152.0 binary runs with temporary HOME/CODEX_HOME. Python is 3.13.12. The candidate remains on the existing unre-based branch, uncommitted and undeployed. Upstream comparison remains the dated assessment in UPSTREAM_REASSESSMENT.md; no new upstream research or public posting occurred during this fix.

The implementation addresses the demonstrated live-quota failure and adds negative coverage for its safety boundaries. It cannot promise all future provider/client changes or every possible failure are covered. Opaque context reconstruction and migration of account-owned files remain outside this verified recovery contract.
