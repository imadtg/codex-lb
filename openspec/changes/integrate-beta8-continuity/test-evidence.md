# Continuity scenario evidence audit

This audit separates observed inputs, desired recovery policy, and proved behavior.
Tests are not evidence for their own requirements. Unmodified beta.8 (`bb4db9d0`)
is the reference implementation; candidate behavior is not an oracle.

## Sources

- C1: Codex 0.152.0 source, `codex-rs/core/src/client.rs`: module documentation
  describes `generate=false` prewarm; lines 305–328 document a per-turn OnceLock
  for the first server-issued turn token. The token is not fabricated or replaced
  by the harness. Source checkout: `../codex-running-0.152.0`.
  Inspected source commit: `316795b3cf2a45e90d121d9f46499d4658b2645c`.
- C2: Same source, `core/src/tools/spec_plan_tests.rs` lines 332–355:
  namespaced function declaration includes namespace name/description and nested
  function schema. The namespace process case uses a function call and matching
  output, not a custom call mislabeled as a namespaced function.
- U1: https://github.com/Soju06/codex-lb/issues/1707 — unavailable hard owner
  while another account works.
- U2: https://github.com/Soju06/codex-lb/pull/2374 — proposed definitive rejection
  versus ambiguous dispatch recovery. Proposal, not a deployed protocol guarantee.
- U3: https://github.com/Soju06/codex-lb/pull/2397 — request-time owner retirement;
  only proxy-injected anchors qualify for that particular retirement path.
- U4: https://github.com/Soju06/codex-lb/pull/2384 — refusal diagnostics and exact
  error assertions; diagnostics alone do not demonstrate recovery.
- U5: archived upstream #2069 review, `../audit-artifacts/continuity-observability/upstream/repos_Soju06_codex-lb_issues_2069_comments.json`:
  maintainer review round 20 identifies a real `automation_update` heartbeat
  without `call_id`, supports the core change, and requests an exact-manifest
  guard against treating it as a tool call. The author reports fix `511786b1`.
  This is precedent for the heartbeat allowance and guard, not proof of its
  current merge status or endorsement of this entire fork.
- L1: `../audit-artifacts/owner-quota-after-recovery-20260912.md` — 09:15:59 UTC
  proven context, stale-owner recovery, replacement quota rejection, then missing
  proof on identical full resend. This is a sanitized incident chronology; the
  referenced `/tmp` source logs may have been lost on reboot.
  Reverified from persistent user journal: `journalctl --user -u codex-lb
  --since '2026-09-12 10:15:55' --until '2026-09-12 10:16:12'`. Local timezone
  UTC+1. Observed proof loss and replay counts match this chronology.
- L2: `../codex-lb-beta7-integration/openspec/changes/archive/2026-09-12-prove-plaintext-agent-followups/context.md`
  — observed 452-item prefix/504-item resend and agent deliveries. Actual incident
  includes encrypted agent content; plaintext-only reduction is not the full incident.
- E1: archived CLIProxyAPI #5530/#5609 under
  `../audit-artifacts/continuity-observability/upstream/`: alias eligibility and
  restored-quota cooldown reports. Related selection bugs, not proof of codex-lb
  transcript portability or permission to ignore a cooldown.
- D1: https://developers.openai.com/api/docs/guides/function-calling — tool
  output is returned with its corresponding call ID. This supports preserving
  call/output identity; it does not establish cross-account opaque portability.

## Findings from independent client-source inspection

Codex `client.rs` lines 1828–1874 explicitly distinguish logical rollout history
from actual wire input after an untraced prewarm. A successful prefix match sends
only incremental items with the warmup response ID. The old fresh-session mock
sent prefix plus suffix with that ID, so it cannot by itself prove the ordinary
Codex path. The corrected recovery proposal failed with the original sequenced
capacity error. We removed the local sequence/prewarm extension rather than
claiming that the old mock proved it. `fresh_prewarm_capacity_refusal` now checks
the unchanged upstream contract: contiguous sequence numbers, one response start,
the exact capacity terminal, and no alternate dispatch. Both versions pass.

The failed-replacement prototype initially returned previous_response_not_found
even for unanchored input. That provider behavior was invalid and its result is
discarded. Version 2 rejects that anchor only when present, echoes the actual
server-issued first turn token, and returns quota when the original account is
contacted without the stale anchor. A newly imported eligible third account then
tests whether the identical resend is stranded. This is a reduction of L1:
explicit stale-anchor rejection replaces the earlier ambiguous disconnect; it is
not yet an exact reproduction of every event in the incident.

## Existing public-process cases

| Case family | Evidence and purpose | Classification |
|---|---|---|
| quota_bridge | U1/U2: completed tool turn, quota rejected before creation, full-history replacement and next turn | desired recovery; observed failure shape |
| quota_bridge_healthy | Same completed tool turn and full-history follow-up with no rejection | counterfactual control: ordinary healthy continuation must work and remain on owner |
| quota_bridge_plain_prefix | Same quota failure without historical developer records or agent deliveries | isolates ordinary quota handoff from the additional portability allowances |
| quota_bridge_agent_message_plain_prefix | Ordinary prefix plus agent delivery | removes historical developer metadata as a confounder |
| quota_bridge_namespace_plain_prefix | C2: nested local function declaration, actual returned namespaced call, matching result | namespace portability without historical developer metadata |
| quota_bridge_failed_event | Same rejection delivered as response.failed rather than error | protocol envelope boundary; provider must give a coherent terminal frame |
| quota_status_agent_message | HTTP quota response and observed plaintext agent input (L2) | separate transport; not interchangeable with bridged WS |
| turn_state_agent_message_chain / suffix_agent_chain | C1/L2: cached first token, old versus newly delivered agent input, two handoffs | distinct prefix/suffix validation and ownership lifecycle |
| turn_state_chain_reconnect | C1/U1: replacement socket closes after completion; reconnect must remain usable | lifecycle boundary, not transport ambiguity during execution |
| suffix_agent | L2 plaintext reduction, completed tool batch then external agent delivery | meaningful minimal reproducer, not full encrypted incident |
| *_encrypted | L2 contains opaque content whose cross-account semantics are unproved | conservative local policy control, not proven provider impossibility |
| *_missing_output | Outstanding tool call without its result | adversarial safety control; not claimed to be ordinary valid Codex output |
| *_changed_prefix | Stored history and submitted history disagree | proof-invalidation control; compaction/edit may be legitimate, blanket refusal is not universal contract |
| owner_unavailable | U1/U3: explicit anchor with only a new user message after pausing owner | current no-reconstruction contract; may evolve if U2 lands |
| *_accepted_failure | Response created before quota error | must not enter the PRE-CREATED quota branch; not a universal ban on all accepted-response recovery |
| quota_bridge_visible_failure | Created response, delivered text delta, then quota error | preserve delivered text exactly once and do not dispatch on another account |
| fresh_prewarm_capacity_refusal | C1: completed prewarm, real incremental suffix accepted then capacity rejected | upstream sequencing refusal control; recovery extension removed |
| replacement_exhausted / accepted / ambiguous | L1/C1/U2: stale-anchor rejection, then B rejects quota, accepts, or disconnects; C becomes eligible | receipt rollback positive with acceptance/ambiguity counterfactuals |

## Missing proof that must not be claimed complete

- L1 exact initial eventless-disconnect prelude (the explicit stale-anchor reduction
  now reproduces subsequent missing proof and owner-unavailable error).
- Model eligibility: spare-model quota must not count as requested-model capacity.
- Quota restored earlier than a prior reset prediction, using real public refresh
  mechanisms rather than mutating cached state or advancing private clocks.
- Account-owned file, concurrent pending requests, and actual process restart
  during/after recovery still lack coverage in this public-process catalog.
  Visible-output failure is covered by its dedicated process control.
- Namespace process coverage uses C2 and asserts the existing forwarding contract:
  call namespaces/IDs are removed and declared tools retain the initial normalized
  manifest (including default `strict=false`). Heartbeat provenance is U5; its
  detailed malformed shapes remain supplementary helper coverage.

## Helper and historical test disposition

- `test_agent_followup_proof`, `test_plaintext_agent_message_replay`,
  `test_historical_prefix_proof`, `test_retained_tool_batch_followups`: retain
  concise classifier safety coverage; process cases above are the behavioral
  oracle. Multiple malformed-field variations need not each launch a server.
- `test_quota_handoff_admission`: internal guard tests cover acceptance, fencing,
  concurrent requests and file ownership. Only pre-created/accepted/visible and
  failed-replacement boundaries currently have process evidence here. Do not
  claim process coverage of the remaining guards.
- `test_replay_sequence`: removed with the unsupported sequence extension. The
  public native-WebSocket prewarm refusal control replaces the misleading claim.
- `test_unanchored_plaintext_replay`: tests a private projection policy; upstream
  retirement replacing its caller must be evaluated separately. A helper passing
  is not justification for restoring a superseded fallback.
- `test_continuity_*`: logging/redaction/task-scope tests are operational contracts,
  not routing evidence. Their exact log assertions were removed from the public
  routing wrapper; keep them in the focused observability suite.
- `test_codex_binary_continuity`: invokes a real client but still replaces internal
  transport functions. Useful secondary evidence, not a separate-process proxy test.
- `probe_exhausted_recovery`: directly constructs account/cache state and patches
  time. Historical diagnostic only; excluded from source-of-truth process coverage.
- Existing transient-retry/Responses/WebSocket test edits: mixed in-process
  transport fixtures. Retain for settlement/lifecycle regression checks, but do
  not represent their entire matrix as independently validated real-client traces.

## Error assertions

The first tightened oracle incorrectly demanded HTTP 429 for every portability
negative. That conflated quota forwarding with unavailable-owner reporting. The
boundary oracle now permits precisely the explicit quota or owner-unavailable
refusal, records the exact status/code, and independently forbids cross-account
dispatch. The legacy `upstream_unavailable` code is accepted only with its exact
owner-unavailable message. Arbitrary validation or server errors still fail.
This does not excuse owner-unavailable on a proven portable positive case.
Native SSE may already have committed HTTP 200 with a keepalive; its quota
terminal is parsed and required to be the sole error with no completed response.
The changed-prefix control exposed a real candidate/beta.8 error-classification
bug: mandatory-owner retry selection returned `no_accounts`, which was rewritten
to `stream_incomplete`. The retained fix forwards the original quota terminal
only for definitive pre-created quota rejection and selection exhaustion; it
captures pre-created status before retry staging can reset response state.

## Reproducible comparison

`scripts/compare_continuity_process.py` snapshots the exact probe and records its
SHA-256 before running the same case against multiple checkouts. Each report
records the commit and application diff hash, raw synthetic wire results, account
dispatch order, and whether failure occurred in setup or the scenario. Artifacts
live on workspace storage. `--temporary-root` can place disposable databases on
tmpfs, avoiding the machine's small `/tmp` quota and disk-load startup failures.
A failing comparison is deliberately nonzero; no xfail hides it.

Example:

```sh
uv run python scripts/compare_continuity_process.py \
  --checkout . --checkout ../codex-lb-beta8-integration \
  --variant quota_bridge_plain_prefix \
  --variant quota_bridge_replacement_exhausted \
  --variant fresh_prewarm_capacity_refusal \
  --temporary-root /dev/shm/codex-lb-validation.tFbIa0 \
  --artifact ../audit-artifacts/beta8-tests/independent-comparison
```

## Test quality requirements

Use a separate executable, disposable data, public account import/pause/settings
APIs, and loopback providers. Preserve the delivered input/output sequence. Obtain
tool calls and response IDs from delivered responses, not fabricated internal state.
Report setup failure separately from scenario failure. Parse terminal events, not
substrings. Log assertions belong to observability tests. A broken or absent
provider must fail the positive control. Negative controls must identify the
intended refusal, not accept arbitrary 4xx/5xx errors. Classify policy alternatives
explicitly rather than modifying expected outcomes until the candidate passes.

## Verification ledger

Artifacts are outside the checkout at `../audit-artifacts/beta8-tests/`; none
contains production database contents. Counts below are separate runs with
overlapping coverage, not an additive count of unique tests.

| Run | Result | Scope |
|---|---|---|
| `broad-final.log` | 1746 passed, 8 failed, 9 skipped | Broad bridge, Responses, native WebSocket, retry, migration and sticky-session checks; eight stale test expectations were subsequently corrected |
| `final-focused-2.log` | 415 passed, 4 warnings | Durable ownership/retirement, replay proof, admission, diagnostics, Responses and transient retries |
| `projection-final.log` | 10 passed | Corrected unsafe-projection matrix; owner retirement is stubbed in this supplementary unit fixture, not in the process oracle |
| `selection-sse-final.log` | 648 passed, 3 skipped, 1 warning | Load balancing, account eligibility/refresh, selection errors, SSE and native fixtures |
| `bridge-terminal-final2.log` | 95 passed, 969 deselected, 1 warning | Quota, capacity and pre-created retry behavior after the error-provenance fix |
| `bridge-full-final.log` | 1064 passed, 1 warning | Complete bridge unit suite after all application corrections |
| `static-final.log` | All checks passed | Ruff, formatting, ty, architecture, cancellation safety, timing seams, settings tiers, migration topology |
| `openspec-final.log` | 65 passed, 0 failed | Strict canonical-spec validation; active change separately validates strictly |

The broad run's eight failures were reviewed individually: namespace portability,
historical developer IDs, proof-preservation call arguments, and an owner-bound
fixture whose former namespace restriction no longer represented ownership.
The replacement owner-bound fixture uses an actual vector-store-backed tool.
An integer developer ID still exercises malformed metadata. The isolated
projection unit's empty-database dependency was removed by explicitly arranging
an owner that can return within its request budget; repository and process tests
exercise retirement separately.

Nine broad skips are PostgreSQL migration tests; PostgreSQL was not available.
The broad SQLite run emitted shutdown-thread warnings and is not evidence of
warning-free database teardown. The process tests demonstrate routing and wire
contracts with synthetic providers, not successful inference against real accounts.

The final matrix is recorded below when complete.
