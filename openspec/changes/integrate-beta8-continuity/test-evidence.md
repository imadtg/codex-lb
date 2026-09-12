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
Codex path. The process probe now sends the suffix and requires recovery to rebuild
the observed prewarm prefix. This correction is intentionally independent of
  whether our current implementation passes.

The corrected prewarm probe currently fails on the candidate with the original
sequenced capacity error and no successful replacement. This is a meaningful
failure of a proposed behavior, not evidence that upstream promises to support it.

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
| fresh_prewarm_capacity | C1: completed prewarm, first real turn accepted then capacity rejected, available alternate | proposed extension of upstream sequencing policy, process proof pending |

## Missing proof that must not be claimed complete

- L1 exact initial eventless-disconnect prelude (the explicit stale-anchor reduction
  now reproduces subsequent missing proof and owner-unavailable error).
- Model eligibility: spare-model quota must not count as requested-model capacity.
- Quota restored earlier than a prior reset prediction, using real public refresh
  mechanisms rather than mutating cached state or advancing private clocks.
- Visible output followed by failure, account-owned file, concurrent pending
  requests, and actual process restart during/after recovery.
- Namespace tools and scheduled heartbeat allowances currently have helper tests;
  namespace process coverage is now added using C2. Scheduled heartbeat shape has
  not been independently established from the inspected client source; do not
  treat the permissive implementation or its helper tests as sufficient evidence.

## Helper and historical test disposition

- `test_agent_followup_proof`, `test_plaintext_agent_message_replay`,
  `test_historical_prefix_proof`, `test_retained_tool_batch_followups`: retain
  concise classifier safety coverage; process cases above are the behavioral
  oracle. Multiple malformed-field variations need not each launch a server.
- `test_quota_handoff_admission`: internal guard tests cover acceptance, fencing,
  concurrent requests and file ownership. Only pre-created/accepted/visible and
  failed-replacement boundaries currently have process evidence here. Do not
  claim process coverage of the remaining guards.
- `test_replay_sequence`: arithmetic/invalid-sequence unit controls remain useful,
  but are insufficient while the feasible fresh-prewarm process case is red.
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

## Reproducible comparison

`scripts/compare_continuity_process.py` snapshots the exact probe and records its
SHA-256 before running the same case against multiple checkouts. Each report
records the commit and application diff hash, raw synthetic wire results, account
dispatch order, and whether failure occurred in setup or the scenario. Artifacts
and disposable databases live on workspace storage, avoiding the machine's small
`/tmp` quota. A failing comparison is deliberately nonzero; no xfail hides it.

Example:

```sh
uv run python scripts/compare_continuity_process.py \
  --checkout . --checkout ../codex-lb-beta8-integration \
  --variant quota_bridge_plain_prefix \
  --variant quota_bridge_replacement_exhausted \
  --variant fresh_prewarm_capacity \
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
