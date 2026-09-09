> **September 9 follow-up:** The previously failing live-quota tests now pass on both transports. See [LIVE_QUOTA_HANDOFF.md](LIVE_QUOTA_HANDOFF.md) for the fix, negative tests, settlement checks and remaining limits. Earlier failure results below are historical.

# Draft: Codex 0.152 portable full resends fail owner recovery because of normal request metadata and namespace normalization

Current assessment: [UPSTREAM_REASSESSMENT.md](UPSTREAM_REASSESSMENT.md). A newly isolated live-quota continuation path still fails the no-extra-client-retry assertion; do not submit this draft as closing the whole tracking issue. [Diagnostics and reproduction](OBSERVABILITY.md).

Refs #1707. Separate, partial fixes; no claim to solve opaque-compaction migration.

A Codex 0.152 / T3 thread on codex-lb 1.25.0b4 remained unusable while two replacement accounts had quota. Pausing the exhausted account and recreating the T3 provider session restored it (user verified). The live instance was not changed during this investigation.

The failure has independently reproducible contributors beyond the anchor fixes shipped in beta.2/beta.5:

1. `replay_safety.py` accepts only effort/summary in reasoning. Codex 0.152 emits `reasoning.context: "all_turns"` for Responses Lite. That setting alone prevents a complete full resend from switching off an unavailable owner.
2. The client-metadata allowlist omits Codex-generated session_id, thread_id, turn_id, parent_turn_id and root_turn_id. These are correlation metadata, not response-owner tokens. Several were present in the last retained pre-incident request.
3. Normal local namespace tool declarations, defer_loading, and namespaced completed calls are rejected.
4. Dispatch strips replayed call namespaces, and its stored input fingerprint describes that representation. Full-resend prefix verification hashes the unstripped input. Fixing only the namespace validator leaves the thread stranded.

5. Poison abandonment and both response-anchor retirement methods clear replay proof along with the rejected anchor, making later portable resends harder to validate. Preserve that proof only on the same account under the existing owner/epoch/anchor fences. For already affected rows with neither count nor fingerprint, allow only explicitly unanchored, fully validated portable history; never override a known prefix mismatch.

6. Namespace-root resource scanning descends into function parameter schemas. Ordinary property names such as `image_url` and `file_id` falsely classify local tools as account-owned. Validate each namespace child and its real resource fields independently; parameter-schema property names are not resource values.
7. Boolean `web_search.external_web_access` and `indexed_web_access` emitted by Codex are rejected. Accept these explicit controls only as booleans.
8. Retaining a pending-tool manifest in storage is insufficient if decoding drops it when the current response anchor is absent. Decode the retained manifest with its recorded nonblank response ID, while still rejecting a mismatch against a different live anchor.

An unmodified Codex 0.152.0 process reproduced the namespace-schema and web-search failures against the real codex-lb route and selector. The final optional integration test uses temporary HOME/CODEX_HOME, a disposable database and loopback stubs. A completes a tool turn, A becomes unavailable, and B completes the continuation with the original tool result. Both HTTP and WebSocket upstream cases pass, with no second dispatch to A (2 passed, 28.49s).

The combined candidate is based on upstream main `d3f63331`, including #2078. It also integrates the production changes and regressions from [#2121 (Irvinwop)](https://github.com/Soju06/codex-lb/pull/2121), [#2069 (msmahdinejad)](https://github.com/Soju06/codex-lb/pull/2069), and [#2111 (dpearson2699)](https://github.com/Soju06/codex-lb/pull/2111). Those changes are upstream authors' work, locally conflict-resolved and tested together, not original contributions of this audit.

## Reproduction

The new `tests/integration/test_thread_continuity_matrix.py` uses the real ASGI route, selector and disposable SQLite. Only credential refresh and upstream sockets are faked. It establishes account A's thread, makes A paused/rate-limited/quota-exceeded, provides healthy B, and resends the full conversation under unchanged session/thread headers.

- Plain complete history recovers.
- Add reasoning.context=all_turns: before the patch, 502 previous_response_owner_unavailable.
- Add normal Codex client metadata: same failure.
- Add namespace declarations: same failure.
- Include namespaced completed history: remains broken after a validator-only patch; recovers after matching the existing forwarding representation.
- Opaque compaction, orphan outputs and previous-response-only deltas remain ineligible for unsafe forwarding.

The exact incident's failing full request was not retained. Its last successful retained operation (08:41:27 UTC) demonstrates the reasoning and correlation fields, not the complete failure-window transcript. The synthetic regressions prove those fields independently trigger the failure surface.

## Patch scope

Accept the explicitly known client controls and local namespace shapes, keep unknown/account-scoped state rejected, and compare fingerprints using the same established forwarding normalization. Keep the raw-hash match for compatibility; do not rewrite durable rows. Preserve rejection of changed arguments, call IDs, names or results.

The wider bridge suite previously used namespaces as the only account-bound property in four same-owner/circuit fixtures. Those fixtures now use a hosted file-search resource to retain their original ownership/fencing assertions, while new real-selector tests cover portable namespaces.

## Separate issue: excluded owner waits (#2163)

The candidate also demonstrates a distinct fix for selector ambiguity: report hard_affinity_owner_excluded when the attempt's exclusion set contains the resolved hard owner. Do not wait for that impossible selection. Keep ordinary hard_affinity_saturated recovery and the existing bounded SSE same-owner retry. This should be submitted separately from request compatibility.

## Existing upstream fix that matters

Identical in-memory quota state produces ACTIVE/reset=None/used=100% on installed b4 and RATE_LIMITED/preserved-reset/used=100% on main with #2078. No reserve-model assumption is necessary to reproduce it. #2078 fixes a different contributor and should not be credited with fixing the compatibility failures above.

Current validation results and review boundaries are recorded in `FINAL_VALIDATION.md`; earlier runs are in `context.md`. No production deployment, live inference, external comment or PR submission was performed.
