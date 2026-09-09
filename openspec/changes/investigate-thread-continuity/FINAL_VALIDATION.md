> **September 9 follow-up:** The previously failing live-quota tests now pass on both transports. See [LIVE_QUOTA_HANDOFF.md](LIVE_QUOTA_HANDOFF.md) for the fix, negative tests, settlement checks and remaining limits. Earlier failure results below are historical.

# Integrated continuity candidate — 2026-09-09

> September 9 observability follow-up revises the completeness claim: normal pause via the real API passes, but an explicit quota rejection on the live owner still needs an extra client request on both transports. See [OBSERVABILITY.md](OBSERVABILITY.md) for the failing reproduction and [UPSTREAM_REASSESSMENT.md](UPSTREAM_REASSESSMENT.md) for current main/PR status. Earlier results below remain historical evidence, not a comprehensive certification.

## Result and operating boundary

The isolated candidate recovers the reproduced portable-history owner-loss paths across paused, rate-limited and quota-exhausted accounts. It preserves tool calls/results, validates the whole replay, and prevents an attempt-excluded hard owner from entering an impossible saturation wait. This is implemented code with route regressions, not a quota-setting workaround.

Base: upstream main `d3f63331d6ba5e233001fb38c9a059e5a9b681cb`, confirmed via GitHub commit API on September 8 (not a claim that main remains unchanged). It includes #2078, which was merged after beta.5 and prevents fresh-but-exhausted usage from clearing the rate-limit state/reset deadline. Branch: `investigate/thread-continuity`. Working changes are uncommitted; nothing was published or deployed.

No live instance restart, inference, account modification or real session/database edit was performed during this follow-up. Synthetic tests use disposable SQLite. The actual Codex probe uses an absolute versioned binary, temporary HOME/CODEX_HOME, no real credentials and a loopback provider. Earlier in the investigation a normal `codex --version` wrapper was invoked and interrupted after discovering that it runs global mise update commands; do not use that wrapper for reproduction. No claim is made that this wrapper invocation was read-only.

## Codex-lb-only follow-up

Scope is strictly codex-lb. All exploratory T3 code/tests were reverted; the T3 checkout is clean. No T3 patch or client restart is a prerequisite for this candidate.

A new optional real-binary integration test runs Codex 0.152.0 against the actual codex-lb ASGI route, real selector and disposable database through a loopback HTTP relay. It establishes a tool turn on A, makes A unavailable, admits B and verifies full-history recovery with the completed tool result. Both upstream transports passed: HTTP and the explicitly selected WebSocket bridge (**2 passed, 28.49s**). Each uses two client HTTP requests and makes no second dispatch to A. This is an optional integration test: set CODEX_LB_TEST_CODEX_BINARY to the absolute versioned binary path; without it these tests skip. No Codex wrapper is invoked.

This probe exposed two additional Codex compatibility defects: namespace-child parameter-schema property names such as image_url were scanned as owned-resource values, and boolean web_search.external_web_access/indexed_web_access were rejected. Both are fixed with strict negative tests (14 passed). The manifest proof itself was correct: an early synthetic fixture omitted output_item.added and therefore could not certify the tool lifecycle; the final fixture emits added/done/completed.

Response-anchor clearing also erased completed transcript proof through two paths besides poison abandonment. Both now retain proof under existing fences. The manifest decoder recognizes retained proof when the live response anchor is absent, while a different non-null response ID still rejects a stale manifest. Replay/durable suite: 310 passed; the 14 new control cases are a separate overlapping run. Final focused denied-anchor/poison/anchor-invalidated regressions: **64 passed, 996 deselected, 4.76s**. Types, lint, formatting, architecture, timing seams, cancellation safety and strict change validation passed again on September 9. Persistent logs are in `../../../../audit-artifacts/continuity-final/` relative to this document.

The first real-client probe unintentionally exercised native HTTP bypass and attempted the test-configured example.invalid upstream before its transport was stubbed. This did not contact a real account/provider. The final probe stubs both upstream transports and uses synthetic credentials only.

## Reviewable concerns and provenance

| Concern | Implementation | Provenance / upstream status at inspection |
|---|---|---|
| Exhausted account reactivation | Existing main load-balancer recovery | [#2078](https://github.com/Soju06/codex-lb/pull/2078), merged after beta.5; already in base |
| Codex replay compatibility | Explicit reasoning.context and correlation fields; local namespaces, defer_loading, completed namespaced calls | New audit fixes. [#1431](https://github.com/Soju06/codex-lb/pull/1431) is precedent for all_turns; [#1578](https://github.com/Soju06/codex-lb/pull/1578) establishes namespace stripping at dispatch |
| Prefix equivalence | Compare exact fingerprint, then established namespace-stripped wire representation | New audit fix; changed arguments, results and IDs remain rejected |
| Completed tools + new user input | Exact durable manifest proof, whole-body validation remains mandatory | [#2121](https://github.com/Soju06/codex-lb/pull/2121), Irvinwop; code/tests integrated. Open: maintainer identifies spec conflict and contributor-attribution CI blocker |
| Unanchored early quota failure | Project complete portable history before imposing a retained owner | [#2069](https://github.com/Soju06/codex-lb/pull/2069), msmahdinejad; code/tests integrated. Open at inspection; do not infer a backend limitation from merge status |
| Owner publication race | Publish real upstream response ownership before downstream delivery; exclude synthesized response IDs | [#2111](https://github.com/Soju06/codex-lb/pull/2111), dpearson2699; code/tests integrated. Maintainer verifies fix and identifies current-main conflicts as blocker |
| Attempt-excluded hard owner | Typed hard_affinity_owner_excluded result, distinct from recoverable saturation | New audit fix; [#2163](https://github.com/Soju06/codex-lb/issues/2163) and merged [#2150](https://github.com/Soju06/codex-lb/pull/2150) are related |
| Poison abandonment and legacy rows | Preserve count/fingerprint/pending manifest only on the same fenced owner; permit validated unanchored history when old rows have neither count nor fingerprint | New audit fix. Do not override known fingerprint mismatch, explicit owner state or file binding |

These are separate review concerns. They are **not yet atomic commits**. Shared replay-safety hunks must be separated when preparing upstream submissions; the combined checkout is the integration candidate. Upstream authors retain attribution. The upstream spec deltas were incorporated into this active OpenSpec change; the raw imported spec patches remain under `imported-specs/` as provenance.

## Completed validation

| Run | Result |
|---|---|
| September 9: expanded owner-loss route matrix + replay safety + durable sessions | **366 passed**, 162.38s (46 route cases + 320 unit cases) |
| September 9: denied-anchor, poison and invalidated-anchor focused regressions | **64 passed**, 4.76s |
| September 9: actual Codex process through real codex-lb route, HTTP and WebSocket upstreams | **2 passed**, 28.49s |
| Diagnostics, owner exclusion, replay safety, SSE, proxy utilities, durable sessions, load-balancer concurrency | **1,932 passed**, 280.64s |
| Real HTTP route + real selector + disposable SQLite owner-loss matrix | **40 passed**, 275.15s |
| WebSocket accepted/partial-output/owner retry regressions | **22 passed**, 67.83s |
| Load-balancer recovery/quota/model/exhaustion cases | **123 passed**, 4.55s |
| Integrated goal-followup, stale-anchor, poison and abandonment selection (earlier combined run) | **93 passed**, 289.91s |
| Imported quota/publication focused route cases (earlier run) | **15 passed**, 115.53s |
| HTTP response/transient route suite (earlier run) | **146 assertions passed, 2 teardown errors**; both affected tests rerun after removing global asyncio.sleep mocks: **2 passed**, 13.23s |
| Real Codex 0.152.0 synthetic tool/reconnect probe | Exit 0, completed; exactly one tool call and result preserved in full resend |
| Types | `uv run ty check`: passed |
| Architecture, timing seams, cancellation safety | Passed |
| OpenSpec | Active change strict validation passed; **58 existing specs passed** |

Counts overlap across selected runs; do not sum them as distinct tests or call this full-repository CI. No strict xfails remain in the new diagnostic/matrix tests. Two old teardown failures were caused by replacing shared asyncio.sleep with a no-op, affecting the application lifespan monitor; the mocks were removed rather than weakening production cancellation.

The explicit-turn-token matrix initially used an unregistered token on the follow-up, which selected a new session and did not establish the supposed old-owner condition. The corrected fixture establishes the token on the first request. All three unavailable-owner cases then reject account transfer. The legacy exception checks the incoming header directly, independently of mutable recovery bookkeeping.

## Actual client recovery witness

Codex 0.152.0, temporary home, synthetic upstream only:

1. Socket 1: prewarm, zero inputs, no anchor.
2. Socket 1: first generation, three inputs, prewarm anchor.
3. Provider completes a synthetic exec_command (`echo SYNTHETIC_TOOL_42`).
4. Socket 1: tool-result continuation, one input and previous-response anchor. Provider closes 1012.
5. Socket 2: **five input items, no anchor**, exactly the completed call/result pair; generation completes.

The probe asserts completion, two sockets, no replay anchor, exact call-ID pairing and retained synthetic tool output. This validates the real client reconnect path, not the entire T3/proxy stack or provider acceptance of encrypted artifacts.

## Reproduction

```sh
uv run pytest -q tests/unit/test_continuity_diagnostics.py \
  tests/unit/test_continuity_owner_exclusion.py tests/unit/test_replay_safety.py \
  tests/unit/test_sse.py tests/unit/test_proxy_utils.py \
  tests/unit/test_durable_bridge_sessions.py tests/unit/test_load_balancer_concurrency.py \
  --timeout=30 --tb=short
uv run pytest -q tests/integration/test_thread_continuity_matrix.py --timeout=30 --tb=short
uv run pytest -q tests/integration/test_proxy_websocket_responses.py \
  -k 'accepted or after_output_item or skips_in_progress' --timeout=60 --tb=short
uv run pytest -q tests/unit/test_load_balancer.py \
  -k 'recovery or quota or model or exhausted' --timeout=30 --tb=short
uv run python scripts/probe_codex_reconnect.py \
  /home/imad/.local/share/mise/installs/codex/0.152.0/bin/codex
CODEX_LB_TEST_CODEX_BINARY=/home/imad/.local/share/mise/installs/codex/0.152.0/bin/codex \
  uv run pytest -q tests/integration/test_codex_binary_continuity.py --timeout=65 --tb=short
uv run ty check
uv run python scripts/check_proxy_architecture.py
uv run python scripts/check_proxy_timing_seams.py
uv run python scripts/check_cancellation_safety.py
```

Incident/runtime versions: codex-lb 1.25.0b4 initially, beta.5 on recurrence per user; Codex 0.152.0; T3 server 0.0.41-nightly.20260908.1387; recovery auth CLI 0.0.40-nightly.20260907.1359; Node 26.7.0; uv 0.12.5. Tests: Python 3.13.12; OpenSpec 1.11.0. The candidate's base SHA is more precise than a beta label.

## Remaining product gaps

This candidate does not establish “every thread can always transfer accounts.” A delta omits earlier history; an opaque checkpoint cannot be reconstructed by pretending it is plaintext. Account-uploaded resources need authorized re-upload or a supported portable reference. Partial provider acceptance needs reconciliation before a retry can be called duplicate-free. Negative tests preserve these boundaries.

Full-stack certification and supported checkpoint/file reconstruction are not claimed. T3 changes are outside scope. T3 source already tests fatal WebSocket stderr -> runtime.error and stopSession scope cleanup, but those tests alone do not prove automatic recreation after a stale session. The original T3 recovery thread supports a separate lifecycle failure after externally killing Codex; no T3 lifecycle patch is claimed here.

The exact beta.5 recurrence's full client resend was not retained, and thread correlation remains unconfirmed. Its retained three-item anchored delta cannot prove that portable history reached the proxy. The candidate fixes independently reproduced contributors, including proof erasure; it does not claim a captured replay of that exact incident. No unconditional permanence guarantee follows from mocked upstreams or local green tests.
