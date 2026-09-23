# Local continuity replay relaxations

This page records places where this fork admits a cross-account Codex replay
that published codex-lb `v1.25.0-beta.8` (`bb4db9d0`) rejects. These are narrow
protocol allowances, not a presumption that arbitrary retained state is
portable. Each allowance keeps its own shape checks and negative controls.

The detailed beta.8 comparison and source ledger remain in
[`openspec/changes/archive/2026-09-13-integrate-beta8-continuity/test-evidence.md`](../openspec/changes/archive/2026-09-13-integrate-beta8-continuity/test-evidence.md).

| Local allowance | Boundary | Evidence level |
|---|---|---|
| Exact settled direct-tool batches can establish a complete resend, including bounded commentary and later turns | Every persisted call must have one matching terminal output; order, prefix fingerprint, and pending-call manifest must agree | Disposable public-process provider scenarios plus incident logs |
| Fingerprinted historical developer metadata can survive projection | Only validated `turn_id` / `content_item_kinds` metadata in positions bounded by the tool lifecycle | Disposable public-process scenarios and Codex-shaped histories |
| Plaintext `agent_message` deliveries can act as fresh follow-up input | Exact author, recipient, content, and metadata shapes; they never count as retained assistant output | Incident-derived process scenarios and classifier controls |
| Codex namespace declarations and call identity can survive account handoff | Nested tools are recursively validated; provider projection remains separately closed | Codex source plus disposable public-process scenarios |
| The exact host `codex_app.automation_update` heartbeat can act as fresh input | Exact field set, heartbeat XML shape, finite timestamp, and no unsettled call | Upstream maintainer review evidence plus malformed-shape controls |
| Encrypted collaboration `agent_message` delivery can move between ChatGPT accounts | Exactly `[input_text envelope, encrypted_content]`; ciphertext is nonblank and preserved verbatim; all response-owned item IDs and the old response anchor are removed | Direct OpenAI valid/corrupt experiment, Codex source, helper tests, and an HTTP-bridge regression |
| A pre-visible permanent credential rejection releases a soft dispatch owner | Only an unanchored full resend may move; the handoff unlinks top-level source item IDs but preserves reasoning, search records, tool outputs, and nested values; previous-response, turn-state, and file owners remain strict | Read-only production trace reduction, two Free-to-Free Luna repetitions, and public-route regressions |
| Completed reasoning and search records remain in an account handoff projection | The projection removes only top-level source item IDs; reasoning ciphertext must be nonblank, search records must be completed, and explicit file/container/vector-store/MCP references still reject the replay | 100-pair same-account control versus 100-pair cross-account Luna experiment |

The first five allowances landed earlier in this fork. Commit `bdf3e5ef` adds
the encrypted collaboration allowance. This ledger should gain a row whenever
another conservative replay rejection is relaxed, including its precise proof
and rollback condition.

## Revoked credential dispatch-owner incident

On 2026-09-16, three unanchored HTTP requests selected an account whose OAuth
token OpenAI rejected as `token_revoked`. Each request carried full compacted
history with retained `reasoning`, so initial dispatch correctly established a
provisional body owner. The forced refresh then permanently disabled that
account and excluded it from the retry pool, but left the provisional owner in
place. Selection therefore required and excluded the same account and replaced
the useful auth failure with `preferred_account_unavailable`, even though other
accounts were serving the same model.

The earlier implementation applied the same replay projection used for quota
handoff when a post-401 forced refresh failed permanently. That projection
omitted reasoning and completed search records. This fork now releases only
the provisional owner and unlinks top-level source item IDs; it sends the full
parsed history, including reasoning ciphertext and completed search records,
to the replacement account. If the request has previous-response, turn-state,
file, or single-account ownership, the owner remains strict.

The route-level regression
`test_proxy_post_401_permanent_refresh_releases_lease_and_portable_history`
recreates the production sequence through `/backend-api/codex/responses`: the
first upstream account returns `token_revoked`, its forced refresh fails
permanently, and a second eligible account receives the ID-unlinked full
history and completes. The regression asserts that reasoning, tool-search,
web-search, messages, and all nested fields survive the handoff.

## Context portability experiment

On 2026-09-22, a disposable direct-OpenAI probe ran twice between two active
Free accounts using `gpt-5.6-luna` and client version `0.156.0`. Every request
used `store: false`, omitted `previous_response_id`, and bypassed codex-lb.
The source and target IDs were hashed before the result was written.

The experiment separately tested hidden reasoning state, web-search history,
and client tool-search history. It compared same-account controls with full
cross-account history, ID-only unlinking, and individual item omission.

The stable findings were:

- Full tool-search history and ID-only unlinking recovered the exact opaque
  deferred-tool marker in both repetitions. Omitting `tool_search_call` and
  `tool_search_output` failed in both repetitions.
- Web-search continuation changed when history was moved across accounts in
  both repetitions, and omitting `web_search_call` also changed it. ID-only
  unlinking preserved the same-account answer in one run but not the other,
  showing that web results and model sampling can vary. The search record
  remains useful context and must not be dropped.
- Hidden reasoning ciphertext was accepted by the target in both repetitions;
  corrupting one character returned `invalid_encrypted_content`. The exact
  hidden-string continuation was stochastic. In a six-history run, full
  cross-account replay matched the one same-account control once. A tighter
  follow-up asked the source and target three times each for two retained
  histories: every target output matched one of the source outputs, while one
  source history itself produced two different outputs. This separates model
  sampling from ciphertext handling. It still does not prove cryptographic
  hidden-state equality, but it does prove that omission is not an equivalent
  context and gives no reason to delete the ciphertext.

The redacted machine-readable evidence is
[`docs/evidence/cross-account-context-portability-2026-09-22.json`](evidence/cross-account-context-portability-2026-09-22.json).
The repeated reasoning controls are recorded in
[`docs/evidence/cross-account-reasoning-repeatability-2026-09-22.json`](evidence/cross-account-reasoning-repeatability-2026-09-22.json).

To test the exact question more directly, a 100-trial Luna matrix asked the
source turn to choose a number from 1 to 100 only in hidden reasoning, then
replayed the same prefix into four independently regenerated second turns:
same-account full history, different-account full history, different-account
ID-only unlinking, and different-account reasoning omission. The source
control returned six recurring values rather than a uniform distribution, so
the paired comparison uses the source result from each trial as its baseline.

The paired association is the primary result: the full cross-account case had
Pearson correlation `-0.025`, Spearman correlation `0.040`, and mutual
information `0.077` bits. Exact agreement was `12%`; mean absolute difference
was `30.8`. Its distribution was `{1: 41, 37: 2, 42: 57}`, versus the
same-account distribution `{1: 2, 37: 1, 42: 27, 47: 10, 57: 38, 73: 22}`.
The total variation distance was `0.70` and Jensen-Shannon divergence was
`0.547` bits. ID-only unlinking and reasoning omission were similarly far from
the source distribution, with total variation distance `0.71` each.

A fair same-account control then used 100 shared prefixes and two independent
continuations on the source account. It produced Pearson correlation `0.788`
and exact agreement `91%` (means `55.04` and `54.63`). The paired
cross-account run produced Pearson correlation `0.075` and exact agreement
`13%` (means `51.20` and `23.14`). The approximately `0.713` drop is the
relevant comparison: independent sampling explains why the same-account
control is below 1.0, while cross-account continuation is close to
unassociated with it. The redacted control artifact is
[`docs/evidence/reasoning-number-same-same-luna-100.json`](evidence/reasoning-number-same-same-luna-100.json).

This is the clearest evidence so far that the target does not reliably recover
the same hidden committed number. The backend still accepted the reasoning
ciphertext in the earlier controls and rejected corrupted ciphertext, so the
safe proxy behavior is to preserve it verbatim while making no promise that
cross-account hidden-state continuity is equivalent to same-account
continuation. The reusable matrix probe is
[`scripts/probe_reasoning_number_matrix.py`](../scripts/probe_reasoning_number_matrix.py),
and its redacted aggregate is
[`docs/evidence/reasoning-number-matrix-luna-100.json`](evidence/reasoning-number-matrix-luna-100.json).
The rerunnable probe is
[`scripts/probe_cross_account_context_portability.py`](../scripts/probe_cross_account_context_portability.py).
It requires four environment variables for disposable source and target
credentials, never reads the codex-lb database, and records no raw model text,
tokens, ciphertext, or account IDs.

## Compaction boundary

On 2026-09-23, a direct `store: false` Luna request supplied a private marker,
sent the complete prefix through `compaction_trigger`, and continued with only
the returned `compaction` item. OpenAI returned HTTP 200 for both operations;
the continuation recovered the marker exactly. The compaction output contained
an opaque 1,484-byte `encrypted_content` field. The redacted result is
[`docs/evidence/compaction-memory-luna-2026-09-23.json`](evidence/compaction-memory-luna-2026-09-23.json).

This establishes that compaction output is essential retained context on its
origin account. It does not establish that a compaction item can be projected
to another account, so the replay gate continues to keep compaction history
owner-bound until a separate cross-account valid/corrupt experiment proves
otherwise. The new reasoning/search relaxation therefore preserves validated
completed records but does not broaden the gate for compaction, hosted state,
files, turn state, or prior-response anchors.

## Encrypted collaboration experiment

On 2026-09-15, a bounded request used one real encrypted collaboration delivery
minted while account A served the source response. The request was sent directly
to OpenAI on a verified-different account B, rather than through codex-lb. The
account identifiers were intentionally not retained in Git. The request used:

- `POST https://chatgpt.com/backend-api/codex/responses`;
- model `gpt-6-astra` and Codex client-version header `0.154.0`;
- `store: false`, no `previous_response_id`, no prompt-cache key, and no tools;
- the original plaintext envelope and 612-byte ciphertext, with response-owned
  top-level item IDs removed;
- a controlled instruction whose expected answer was `DECRYPTED`.

The unchanged ciphertext completed with HTTP 200 and returned the controlled
answer. A second request changed one character in the middle of the ciphertext.
That control emitted `response.created` and then `invalid_encrypted_content`.
The control matters: OpenAI did not merely ignore the opaque part. Its backend
validated or decrypted it, and accepted the unchanged source-account ciphertext
on the alternate account.

This proves portability for the tested ChatGPT account pair and backend behavior
on that date. It does not prove that every future account class, model, or backend
version will accept it. It also does not make `agent_message` portable to model
sources: the separate Codex-to-provider gate still rejects every such item.

The first probes used client version `0.152.0` and were rejected before inference
because `gpt-6-astra` required a newer Codex version. Those attempts say nothing
about ciphertext portability. The successful pair used `0.154.0`.

Relevant versions and provenance:

| Component | Version / identity |
|---|---|
| codex-lb published base | `v1.25.0-beta.8`, `bb4db9d08cc955743735678ccdb8d8bef19f7bea` |
| local implementation | `bdf3e5ef2d248dcf2f6060ec92bac50a8e28c0af` |
| Codex source inspected | `0.152.0`, `316795b3cf2a45e90d121d9f46499d4658b2645c` |
| Installed Codex CLI at experiment time | `0.153.4` |
| Successful request fingerprint | `0.154.0` |
| Requested model | `gpt-6-astra` |
| Python project environment | `3.13.12` |
| OpenAI backend | unversioned service observed 2026-09-15 |

OpenAI Codex PR [#26210](https://github.com/openai/codex/pull/26210) is supporting
protocol evidence: Responses encrypts collaboration arguments, Codex forwards
the ciphertext, and Responses decrypts it for recipient models. The local Codex
source renders an encrypted `InterAgentCommunication` as the same two-part
`agent_message` shape used by the experiment.

The committed evidence summary is
[`docs/evidence/encrypted-agent-portability-2026-09-15.json`](evidence/encrypted-agent-portability-2026-09-15.json).
It intentionally excludes access tokens, raw ciphertext, decrypted content,
full account identifiers, and production database records. Because the direct
experiment shows the ciphertext is decryptable across accounts, raw ciphertext
must be treated as sensitive rather than checked into Git.

## Rerun and rollback condition

Capture an encrypted `agent_message` from a disposable source-account thread as
a standalone JSON object. Keep that fixture outside Git with owner-only
permissions. Then run the direct valid/corrupt pair against a different account:

```sh
export CODEX_PORTABILITY_TARGET_TOKEN='…'
export CODEX_PORTABILITY_TARGET_ACCOUNT_ID='…'

uv run python scripts/probe_encrypted_agent_portability.py \
  --item /secure/path/agent-message.json \
  --source-account-id 'source-account-id' \
  --artifact /secure/path/portability-result.json
```

The script never contacts codex-lb and never reads its database. It sends two
`store:false` requests directly to OpenAI, records only hashes and terminal
classification, and fails unless the original completes with `DECRYPTED` while
the corrupted control returns `invalid_encrypted_content`. Its endpoint is fixed
to the official ChatGPT Codex Responses URL so a mistyped argument cannot send
the access token elsewhere. It also refuses an equal source and target account
unless `--allow-same-account-control` is explicitly supplied.

Re-enable the encrypted-agent rejection if a fresh cross-account valid probe
fails while a second run using the source account as the target and
`--allow-same-account-control` succeeds. Also re-evaluate the allowance if the
corrupt control completes, because that would invalidate the evidence that
OpenAI consumes the ciphertext. A model-version rejection requires updating the
request fingerprint before drawing either conclusion.

The process-level regression is
`test_stream_via_http_bridge_preserves_context_after_owner_unavailable[encrypted-agent-followup]`.
It supplies a fingerprinted prefix, exact pending-tool manifest, matching call
and output, encrypted agent delivery, and fresh user input through the HTTP
bridge. On the preceding fork commit it ends at
`owner_unavailable_replay_rejected` with `reason=missing_prior_output`; on
`bdf3e5ef` it strips the anchor and item IDs, preserves the ciphertext exactly,
excludes the unavailable account, and dispatches the fresh replay.
