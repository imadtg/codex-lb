> **September 9 follow-up:** The previously failing live-quota tests now pass on both transports. See [LIVE_QUOTA_HANDOFF.md](LIVE_QUOTA_HANDOFF.md) for the fix, negative tests, settlement checks and remaining limits. Earlier failure results below are historical.

# Continuity diagnostics — schema 1

## What the candidate records

The `app.modules.proxy.continuity` logger emits INFO events through the existing logging system. No new database, network destination, worker or setting is required. Each new record carries wall time in nanoseconds, process-relative monotonic time in nanoseconds, PID and schema version. These are observations, not scheduling clocks; no nanosecond measurement accuracy is implied.

| Event | Evidence |
|---|---|
| `continuity_decision stage=http_ingress` | Client supplied an anchor or did not; input item count after request-schema normalization and before bridge trimming |
| `continuity_decision stage=payload_portability` | Actual first failed shared-classifier gate, or `accepted`; uses the same implementation as routing |
| `continuity_decision stage=durable_context_proof` | Full-resend recognition, missing proof, prefix mismatch, failed projection, missing retained-output proof, or `context_proven`; stored count and fingerprint/manifest presence |
| `continuity_decision stage=retry_body` | The already-validated projected body was preserved across injection/trim re-preparation |
| `continuity_candidate` / `continuity_candidate_snapshot` | Up to 64 account-state inputs to the sticky selection helper, including usage, reset/cooldown deadlines, status, health and stream count; total/omitted count is explicit |
| `continuity_selection` | Actual public selector result, hashed selected/required account and model; initial candidate/exclusion counts and initial explicit ownership restriction |
| `continuity_proof_mutation` | Committed or fenced-out rebind, denied-anchor clear and ordinary anchor retirement; owner epoch and proof retention policy |
| `continuity_retry` | Pre-created retry ownership gates: hard owner, hard anchor, operation presence, body ownership, preferred-owner requirement, allowed account switch and excluded owner |
| `continuity_terminal` | Upstream terminal observation with request/archive/session/account hashes, event count, retry count and visibility; not proof the client received it |

Existing `http_bridge_event` records additionally have `observer_request` and `observer_scope` hashes, joining decisions to creation, reuse, trim/reconnect, retry-circuit, owner-loss and terminal-error events. The observer fields deliberately describe the task emitting the event: a long-lived reader may retain the first request's context. For terminal attribution use the explicit request/archive IDs, not the reader's observer context. Existing request logs remain the source for usage/reservation settlement and HTTP status.

`accepted` means a body passed portability validation. It does not mean dispatch was authorized or completed. `context_proven` means durable history proof passed, not that all account, file, turn-state, operation, quota and partial-output checks passed.

The reasons distinguish conversation/previous-response/prompt binding, unknown payload fields, reasoning/text/tool-choice/client-metadata controls, input shape, uploaded files, unsupported item types, tool lifecycle/item fields, content shape, account-scoped input, and tool declarations. Input lifecycle reasons now distinguish response-owned IDs, invalid item type/object, metadata, unknown fields, unfinished calls, invalid/duplicate calls, unmatched/invalid results and heartbeat-before-settlement. Nested tool/content rejection is still a gate category, not a logged JSON path. The offline `diagnose_continuity.py` can inspect the actual branch when an authorized private payload is separately available; production telemetry intentionally does not retain that payload.

## Capture and export

Keep this logger at INFO and retain the service's existing logs across restarts. `CODEX_LB_LOG_FORMAT=json` uses the existing JSON format option; text also works. This work did not change the live service, its log level or retention. A process crash, full disk, disabled logger or missing rotated log can still leave an evidence gap. Do not interpret absent records as successful completion.

From the candidate checkout:

```sh
uv run python scripts/continuity_timeline.py /path/to/saved-service.log > continuity-report.json
uv run python scripts/continuity_timeline.py /path/to/saved-service.log \
  --request-id 'the-request-id' --max-events 10000 > continuity-request.json
```

The exporter reads text or JSON lines (`message` field), accepts only the schema-1 event family, allowlists keys and enum values, rejects raw identifiers, and omits unrelated log lines. Output contains a SHA-256 fingerprint of the installed proxy Python source plus package/Python versions. Generate this at capture time: running the exporter from different code describes that code, not the historic server binary. Keep the deployment commit/build digest and Codex/T3 versions alongside the report. The beta package label alone cannot distinguish this uncommitted candidate from stock beta.5.

Identifier hashes follow the existing 12-hex SHA-256 convention. They are correlation pseudonyms, not cryptographic anonymization of guessable IDs. Conversation text, tool arguments/results, raw tokens, unknown field names, account emails and full request bodies are not emitted by the new recorder. The existing broad service logs may contain other data: the exporter does not export arbitrary old log messages. Review any additional raw logs before publishing them.

Export preserves supplied file order, includes process/clock fields and reports truncation. It does not manufacture a definitive root cause from incomplete evidence. Cross-process ordering requires the wall clock; monotonic values are comparable only within the corresponding process lifetime.

## Diagnostic sequence

1. Find ingress and its request hash. Compare the client input count to later existing trim events: a short upstream delta does not prove the client omitted history.
2. Follow durable context proof and payload portability separately. `stored_proof_missing` is different from `prefix_mismatch`; a missing manifest after anchor retirement indicates a different defect than an invalid tool declaration.
3. Find the selector result. Initial candidates are not “eligible accounts with quota”; they precede some admission/owner filtering. Candidate snapshots show only the instrumented selection helper's inputs, not an exhaustive account-by-account policy decision for the entire pool. Model is hashed; match against the model from existing request metadata if needed.
4. Join bridge events and terminal records. A reused bridge can avoid invoking the selector. A successful portability decision followed by pre-created retry failure points to the retry/ownership layer, not the classifier.
5. Inspect proof mutations and owner epochs. `applied=False` is a fence rejection, not a successful clear. `proof_preserved=True` describes the mutation policy, not proof that a complete transcript existed.
6. Confirm client delivery and settlement with existing request logs. An upstream `response.completed` alone is insufficient.

The added events have bounded fields and at most 64 candidate detail lines per helper invocation. They are not sampled. Large pools and frequent selection can produce substantial INFO volume; the omitted count is explicit. No full-payload hashing or extra DB reads are performed for telemetry.

## Reproduction discovered by telemetry

The original optional real-client fixture directly updated disposable SQLite and invalidated one selection cache. It did not invoke the pause API, which also marks the account unavailable in the shared routing cache. That fixture was timing-sensitive: live-socket reuse and new-session selection behaved differently. The normal pause fixture now calls the real local `/api/accounts/{id}/pause` route. **Both upstream transports pass: 2 tests, 7.37s.** This revises the earlier claim based on the direct-DB fixture.

A separate explicit-quota mode admits B but leaves A active until the mock provider rejects the live continuation. It retains the exact two-client-request success assertion, so it visibly fails rather than silently redefining success:

```sh
CODEX_LB_TEST_LOSS_MODE=quota \
CODEX_LB_TEST_CODEX_BINARY=/home/imad/.local/share/mise/installs/codex/0.152.0/bin/codex \
uv run pytest -q tests/integration/test_codex_binary_continuity.py --timeout=65 --tb=short
```

Current result: **2 failed, 25.12s**, both because Codex needed **three** client requests instead of two; the process eventually completed. On the bridge path: ingress full history -> durable proof passed -> projected body accepted -> existing socket reused -> proxy anchor injected and input trimmed -> pre-created retry -> excluded hard owner / durable-operation ownership prevents the attempted reconnect -> client retries again and a fresh session recovers. The detailed rerun identifies `input_response_owned_id` on direct HTTP. On WebSocket, the pre-reconnect snapshot is `hard_owner=True fresh_switch_allowed=False require_preferred=True account_bound_body=True operation_present=True hard_anchor=True owner_excluded=True response_events=0`. Thus portability passed earlier, but the retry separately retained a hard/operation owner that it had excluded. The detailed rerun again failed both no-extra-request assertions (24.82s).

A narrow fix now preserves the already-validated projected replay body across injection/trim; it removes the raw-ID false rejection on that retry. It does **not** bypass the later durable-operation owner guard. Experimental pin relaxations were removed because they did not establish a safe complete handoff. This remaining failure is a blocker to “fully fixed” and comprehensive PR claims; it is not an xfail hidden inside the default passing run.

The synthetic logs and redacted `quota-timeline.json` are in the parent workspace's `audit-artifacts/continuity-observability/`. They are not a replay of the original private incident. All provider connections in these tests are loopback stubs and all accounts/databases are disposable. The versioned Codex 0.152.0 binary runs in a temporary HOME/CODEX_HOME; never use the auto-updating `codex` wrapper for these tests.

## Validation and remaining work

- Classifier/redaction/request-concurrency and replay/durable/selector regressions: **526 passed**, 51.11s.
- Route matrix with ingress/selection/proof log assertions: **46 passed**, 118.26s (before the final retry-body retention addition).
- Focused pre-created, poison and anchor tests: **101 passed**, 10.52s. The run also printed an `AdmissionLease` garbage-collection warning; this is not a clean settlement certification and needs attribution before broad PR readiness.
- Real Codex normal pause via API: **2 passed**, 7.37s.
- Real Codex quota-on-live-owner: **2 failed**, 25.12s; retained as a known failing reproduction.

Counts overlap. This is not full CI, a production rollout, or exhaustive observability of every proxy branch. Remaining observability work includes exact per-account filter rejection stages, nested classifier paths, complete cross-request reader attribution and a guaranteed durable event sink. Those are explicit limits; the current recorder substantially narrows the blind spots and has already identified a previously missed path.

Final post-edit smoke: **20 passed**, 39 deselected, 18.55s; actual-client pause rerun: **2 passed**, 12.17s. Types, Ruff, architecture, timing and cancellation guards passed. OpenSpec validation uses the installed versioned Bun binary because the ordinary Bun shim has no selected version; no global tool configuration was changed.

Detailed-reason classifier and redaction tests: **328 passed**, 9.86s. Pre-created retry telemetry regressions: **37 passed**, 4.51s. Strict OpenSpec validation passed using Bun 1.3.14 / OpenSpec 1.11.0.
