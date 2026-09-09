# Continuity audit — 2026-09-08

## Environment and boundaries

Incident: codex-lb 1.25.0b4, Codex 0.152.0, T3 server 0.0.41-nightly.20260908.1387; recovery auth CLI 0.0.40-nightly.20260907.1359; Node 26.7.0, uv 0.12.5. User confirmed the earlier account-pause + T3 session-stop recovery. Pausing alone was not tested. No live mutation or inference was performed in this audit.

Candidate checkout: `codex-lb-continuity-audit`, branch `investigate/thread-continuity`, base `d3f63331d6ba5e233001fb38c9a059e5a9b681cb` (upstream main, confirmed again during final validation). Tests use CPython 3.13.12 and disposable SQLite, synthetic tokens/accounts, ASGI HTTP requests, and fake provider sockets. Installed beta.4 is imported read-only by a standalone pure-state probe; never run its server. The real database was opened with SQLite `mode=ro` for selected incident records only.

## Incident evidence versus inference

The retained account A had primary usage 100%, secondary usage 16%, while B and C had quota. Logs show poison abandonment, quarantine suppression of the anchor, then continued required-owner selection and circuit reopening. The installed b4 code clears continuity while keeping account identity; the later hard-key path restores the preferred owner even with no previous_response_id. Clearing an anchor is not the same operation as authorizing an account switch.

An identical synthetic post-429 state produces:

| Code | Status | Reset deadline | Primary used |
|---|---|---|---|
| Installed beta.4 | active | cleared | 100% |
| Current main (#2078) | rate_limited | preserved | 100% |

Run `scripts/probe_exhausted_recovery.py` with each interpreter/PYTHONPATH in an isolated directory. It uses only in-memory ORM objects and patched time. This reproduces a defect matching the incident, not proof that every runtime branch of the incident was captured.

There are no retained operation request bodies for the 08:42–08:47 failure window in that bridge row. The preceding 08:41:27 request is retained. Its controls include reasoning.context=all_turns and client_metadata keys session_id, thread_id, turn_id, root_turn_id, alongside existing accepted x-codex metadata. Replacing its input with a synthetic user message and removing previous_response_id/type still fails the current-main classifier. The reasoning check fails first; removing context exposes the metadata rejection. Removing those controls allows the synthetic body. Thus ordinary client controls are independently sufficient blockers. The exact failed full resend and all its history proofs remain unobserved; do not call this a captured end-to-end replay of the incident.

The reserve/Luna-versus-Astra explanation is not established. The inspected b4 additional-quota registry only maps Spark; no applicable reserve override was found. #2078 provides an independently reproduced mechanism without that hypothesis.

## Why some sessions switch and others do not

A proxy can send portable full history to another account. A delta referring to a response ID on the old connection is incomplete. An opaque compaction checkpoint may be the only remaining representation of earlier history; deleting it loses context. Those are real information/ownership boundaries. Separately, this audit found several ordinary Codex fields incorrectly classified as account-bound, and a fingerprint comparing two different representations of the same history. Calling all of these “replay sensitivity” hides actionable bugs.

Codex 0.152 sources establish the field shapes:
- `codex-rs/codex-api/src/common.rs`: reasoning context enum auto/current_turn/all_turns.
- `codex-rs/core/src/client.rs`: sets all_turns for Responses Lite.
- `codex-rs/core/src/responses_metadata.rs`: client-generated correlation IDs.
- `codex-rs/tools/src/responses_api.rs`: namespaces contain function/custom declarations; defer_loading is boolean.
- `codex-rs/protocol/src/models.rs`: optional namespace on tool calls.

## Candidate changes in this checkout

1. Accept those explicit reasoning and correlation fields; still reject unknown controls and opaque turn-state metadata.
2. Validate local namespace children normally, accept boolean defer_loading and optional namespaced completed calls. Hosted resources/nested namespaces/unknown fields remain rejected.
3. Compare a full-resend prefix against both its exact representation and the existing namespace-stripped forwarding representation. Stored hashes are not rewritten. Changed names, arguments, IDs, and results still fail.
4. Pass the attempt's excluded-account set to hard-owner selection. Return hard_affinity_owner_excluded when the resolved owner is excluded; the recovery timer cannot make that selection possible. Preserve the existing bounded SSE same-owner retry and ordinary saturation behavior. This prevents the #2163 impossible wait; it does not by itself reconstruct a nonportable request or promise transparent recovery.

No new settings, migrations, account mutations, history edits, or deployment.

## Failure map and upstream coverage

Status checked via GitHub API on 2026-09-08. “Covered” below names a reproduction or existing test family, not a claim that external services cannot fail.

| Failure boundary | Evidence / coverage | Concrete remedy / status |
|---|---|---|
| Fresh but exhausted quota sample clears a 429 deadline | Side-by-side beta.4/main pure-state probe; load-balancer recovery suite | #2078 merged after beta.5; take upstream fix |
| Normal Codex controls reject portable replay | Real-route owner-loss matrix, reasoning and metadata cases | Candidate explicit validator compatibility changes |
| Namespace declarations/calls reject replay | Unit validator cases plus real-route namespace cases | Candidate validator fix |
| Sent-history fingerprint differs from client history | Namespaced-history route fails before normalization fix; field-change negatives | Candidate comparison uses established forwarding normalization |
| Hard owner excluded by same attempt | Actual selector with legacy and thread ownership; real DB bridge selection loop | Candidate typed non-waitable result; #2163 still open |
| Accepted output-free retry excludes required owner | Existing bridge hard-owner regressions | #2150 merged in beta.5; narrower than all retry paths |
| Poisoned anchor keeps being injected | Quarantine and full-resend regression families; incident logs | #1891 in beta.2, #2072 lifecycle cleanup; owner migration still separately gated |
| Completed tool batch followed by new user input | `responses_input_suffix_matches_pending_tool_calls` requires tool-only suffix | #2121 remains open upstream; its production fix and regression tests are integrated locally, including complete-manifest and missing-result boundaries |
| Unanchored full resend + soft prompt-cache owner + early quota | #2068 reproduction, #2069 route regression proposal | #2069 remains open upstream; its projection and quota-recovery route tests are integrated locally |
| Immediate previous_response_id followup beats owner publication | #2107 / #2111 | #2111 remains open upstream; owner-before-delivery fix and route tests integrated locally, including queued/in_progress lifecycle and synthetic-ID exclusion |
| Frame-less/idle upstream loss poisons account health | #2075 / #2081; existing transport classification tests | Separate transport evidence from provider rejection; no quota/health penalty for an idle client/connection lifecycle failure |
| Sustained actual overload | #2166 | Merged beta.5 isolation/weighting; intentionally does not migrate hard continuity owners |
| Opaque compaction or account-uploaded file | New negative route/unit cases | Client must reconstruct portable context/reupload required files under replacement credentials, or retain rightful owner. Never erase checkpoint content and call it recovery |
| Missing call/result or delta-only history | New negative route/unit cases | Request full local history; preserve completed tool results so retries cannot rerun tools implicitly |
| Partial output already delivered / ambiguous upstream acceptance | Existing accepted-replay, quarantine, operation/manifest mechanisms | Track commitment and operation identity; replay only with protocol-level reconciliation or explicit at-least-once semantics, not blind redispatch |
| Restart, expired cache, replica ownership race, concurrent fork | Existing durable-prefix, stale-owner, epoch, lease, and owner-forwarding test families | Persist authoritative ownership before delivery; compare-and-set account/epoch/anchor changes together; reject stale branch mutations |
| Whole eligible pool exhausted or model unavailable | Selector admission/quota tests | Model-specific eligibility, bounded terminal exhaustion with actual reset metadata; no client reconnect storm |
| T3 adapter/provider state remains stale after upstream failure | Prior user-confirmed recovery needed session.stop | T3 needs automatic provider-session recreation that preserves the logical thread; distinct client integration work, not accomplished by changing proxy quota thresholds |

Tracking issue: https://github.com/Soju06/codex-lb/issues/1707 . Related PRs/issues use the same repository and numbers above. Scope each upstream submission separately; do not label this work as fully fixing #1707.

## CLIProxyAPI comparison and architecture direction

CLIProxyAPI #4522 merged a useful boundary: native incremental continuation stays on its original credential/URL/socket; when that cannot continue, suppress the credential error and close 1012 to request a fresh client replay. Canonical HTTP transcript state is separate; tool-cache updates commit only after success. Reviewed implementation: `sdk/api/handlers/openai/openai_responses_websocket.go` (downloaded v7.2.154 source during the audit).

https://github.com/router-for-me/CLIProxyAPI/pull/4522

This is not an immunity guarantee. #4536 reported a single-credential 429→1012 reconnect/replay loop (now closed); #4639 keepalive and #4643 precommit recovery remained open at inspection. Codex 0.152 maps WebSocket close frames to a stream error; its request builder has full input when no incremental anchor is usable. Neither fact alone proves every T3 recovery path honors 1012. The incident's HTTP bridge cannot forward a WebSocket close code through an HTTP response.

The useful design to port is an explicit recovery contract:
1. Select by requested model, quota and authorization.
2. Track logical transcript ownership separately from replaceable transport and account selection preference.
3. On owner loss before commitment, use a proved portable full body if available.
4. Otherwise emit a bounded full-history-required signal the actual client understands (HTTP and WS separately).
5. Let the client rebuild from local history; checkpoints need a supported portable export/reconstruction path, not deletion.
6. Rebind account/anchor/epoch together only after replacement admission; preserve call results and operation identity.
7. If there is no eligible replacement or no portable reconstruction, finish with one actionable terminal result; do not repeat an impossible transition.

A faithful next protocol harness must include the actual Codex retry state machine and a fake T3 adapter, with faults at acceptance, first output, terminal completion, owner publication, cancellation and reconnect. Provider acceptance of opaque encrypted artifacts across accounts cannot be established by inventing a permissive mock. Keep that boundary explicit and test the client reconstruction path instead.

## Historical validation ledger (before the final integrated candidate)

- Initial baseline: 18 diagnostic unit cases passed; 15 route characterizations passed and the desired namespace recovery assertion xfailed. The original xfail wrapper was replaced with ordinary positive recovery cases before verifying the fix.
- Red witnesses: reasoning-context route returned 502; namespaced-history route still returned 502 after validator-only changes; both excluded-owner selector cases returned hard_affinity_saturated rather than a non-waitable result.
- Candidate targeted run: **717 passed in 168.93s** across diagnostics, replay safety, load-balancer/concurrency, and the new real-route matrix.
- Wider existing bridge selection: initially **31 passed, 4 failed**. All four failures used namespaces as their account-bound fixture; updated those fixtures to hosted file-search state while preserving the same-owner and circuit assertions. Rerun of the whole stale-owner family: **21 passed, 147 deselected in 121.23s**. This overlaps the earlier run; do not add these counts as distinct tests.
- Final diagnostics including the explicit remaining #2121 witness: **64 passed, 1 strict xfailed**. The xfail asserts desired successful proof, not current failure behavior, so resolving the gap will fail the suite as XPASS until the marker is removed.
- Excluded/unavailable owner distinction: **3 passed**, including an unexcluded unavailable owner's retained recovery wait.
- Changed production modules: `uv run ty check` passed; Ruff checks passed after import formatting. `git diff --check` passed.
- OpenSpec 1.11.0: active change strict validation passed; **58 existing specs passed**.
- Latest release checked at the end of the audit: **v1.25.0-beta.5**, published 2026-09-08 07:13:08 UTC. #2078 merged 09:38:06 UTC, after that release. No live upgrade performed.

Reproduce the principal run:

```sh
uv run pytest tests/unit/test_continuity_diagnostics.py \
  tests/unit/test_continuity_owner_exclusion.py \
  tests/unit/test_replay_safety.py \
  tests/unit/test_load_balancer_concurrency.py \
  tests/unit/test_load_balancer.py \
  tests/integration/test_thread_continuity_matrix.py -q --disable-warnings --tb=short
```

The two tests added after the 717-case run are the expected-failing #2121 witness and the passing unexcluded-owner recovery-wait control. Their individual results are recorded above. This is a scoped candidate, not a full-repository CI result or an end-to-end T3/Codex certification.

## Recurrence inspected 2026-09-08 evening (read-only)

User reports recurrence on beta.5 in this conversation; exact T3-thread correlation requested and still pending. Recent journal shows bridge-key hash dac532f146e9:
- 17:53:40 UTC: fresh_reattach_anchor_injected.
- 17:53:43: previous_response_not_found; previous_response_source=proxy_injected; fresh_replay_available=false; owner lookup diagnostics unknown.
- 17:53:47: denied_proxy_anchor_before_dispatch.
- 17:55:14: owner_account_unavailable; another injected anchor fails at 17:55:18; dispatch denied 17:55:22.
- Subsequent reattach attempts repeatedly return hard_affinity_saturated on the same owner, including misleading "Try again in 0s".

The durable row at inspection has latest_input_item_count=NULL. Retained failed operation at 17:55:13 contains only three anchored input items (reasoning, custom tool call, result), not a self-contained full history. The preceding successful operations also use three-item deltas. This does not establish the shape of every incoming client full resend, or when the stored count was cleared. It does establish that the retained delta cannot independently supply the missing transcript. Do not claim the current compatibility patch alone fixes this recurrence. No live recovery/mutation performed.

The candidate was subsequently advanced to upstream main d3f63331 and the upstream fixes integrated. See FINAL_VALIDATION.md for the current results; earlier counts and strict xfail descriptions above are historical. Changes remain uncommitted; no deployment or upstream publication.
