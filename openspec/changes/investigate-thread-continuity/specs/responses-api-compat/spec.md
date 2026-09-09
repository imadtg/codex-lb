## ADDED Requirements



### Requirement: Exact tool-manifest replay preserves fresh user follow-up

When a fingerprint-verified durable input prefix is followed by every call and
matching output in the durable prior-response pending-tool manifest, the
full-resend context proof SHALL permit trailing self-contained user input after
that complete batch. The proof MUST require exact call IDs and call types,
complete settlement, no duplicate or orphan result, and no call-ID collision
with the stored prefix. It MUST reject user input interleaved with the batch or
any later call, output, or instruction-role message after the fresh-input suffix
begins. The existing bounded developer-interleave exception MUST NOT gain a
trailing-input extension.

Account switching MUST still require the complete projected request to pass
account-neutral replay classification, the durable prefix to match, and the
existing pre-dispatch recovery and account-scope checks. A qualifying replay
MUST retain the complete calls, outputs, and fresh input. This proof MUST NOT
authorize transferring encrypted compaction, account-owned files, conversation
references, or an unverified input prefix.

#### Scenario: Goal follow-up after completed tool batch can leave exhausted owner

- **GIVEN** the input contains a verified stored prefix and exactly settles its durable pending-tool manifest
- **AND** a self-contained goal-continuation user message follows the complete tool batch
- **WHEN** the previous owner is unavailable before dispatch and the complete projected body is account-neutral
- **THEN** the bridge can use its existing fresh replay path on another eligible account
- **AND** it retains the calls, results, and goal instruction without the old response anchor

#### Scenario: Fresh input does not conceal a missing parallel result

- **GIVEN** a durable manifest contains multiple calls
- **WHEN** a resend appends user input after only part of the recorded batch
- **THEN** context proof fails and cross-account replay remains forbidden

#### Scenario: New input does not relax developer-interleave bounds

- **GIVEN** a suffix uses the existing three-item custom-call/developer/output exception
- **WHEN** additional user input follows that suffix
- **THEN** this exception remains ineligible for exact-manifest proof

## MODIFIED Requirements

### Requirement: Account-bound retries remain on their dispatch owner

The proxy MUST bind a Responses request body that is not a canonical
account-neutral fresh replay to the account that first receives that exact
body. Every later selection for that request MUST treat the dispatch owner as a
strict required account across HTTP streaming, HTTP bridge, and direct
WebSocket transports.

The proxy MUST NOT exclude the dispatch owner and send the retained body to a
different account during stale-anchor recovery, retryable account failure,
Trusted Access migration or degradation, bridge reconnect, or WebSocket account
switching. If the required owner is unavailable, the proxy MUST fail closed
without dispatching the retained body to another account.

The proxy MAY perform one forced authentication refresh and replay a retained
account-bound body on the same dispatch owner. It MUST NOT use that refresh to
exclude the owner or migrate the body to another account, and a permanent
authentication failure MUST remain terminal for the bound body.

The proxy MAY clear the dispatch-owner binding only after verified recovery
replaces the exact wire body and the replacement passes the canonical
account-neutral-fresh-replay predicate. Removing `previous_response_id` alone
MUST NOT make retained account-scoped input portable.

Proxy-owned operation metadata that will be added at the send boundary MUST
remain bound to the current account unless an explicit operation-rebind path
replaces that identity before account selection. Installing a verified fresh
body and clearing its dispatch-owner binding MUST occur as one state
transition.

#### Scenario: Encrypted reasoning remains on its first dispatch account

- **GIVEN** account A first receives a Responses request containing encrypted
  reasoning or another account-scoped retained item
- **WHEN** a pre-visible retry excludes account A or requests a differently
  authorized account
- **THEN** the proxy does not dispatch the retained body to account B
- **AND** it may dispatch only a verified account-neutral projection that
  removes the account-scoped items and passes the canonical fresh-replay gates
- **AND** the retry fails closed when no such projection is available

#### Scenario: Verified account-neutral fresh replay may change accounts

- **GIVEN** verified recovery removes a stale continuation anchor
- **AND** the exact replacement body contains only canonical account-neutral
  fresh input
- **WHEN** normal retry selection chooses account B
- **THEN** the proxy may dispatch the replacement body to account B

#### Scenario: Confirmed pre-dispatch failure does not create an owner

- **GIVEN** account A is selected for a nonportable Responses body
- **WHEN** transport evidence confirms the request failed before any upstream
  bytes were dispatched
- **THEN** the proxy does not record account A as the dispatch owner
- **AND** normal retry selection may dispatch the body first on account B

#### Scenario: HTTP bridge preserves payload ownership

- **GIVEN** an HTTP bridge request has already dispatched a nonportable body to
  account A
- **WHEN** pre-created recovery or reconnect selection excludes account A
- **THEN** the bridge does not submit that body on account B

#### Scenario: Direct WebSocket preserves payload ownership

- **GIVEN** a direct WebSocket request has already dispatched a nonportable body
  to account A
- **WHEN** retry handling prepares an account switch
- **THEN** the proxy rejects the switch unless the exact replacement body is a
  canonical account-neutral fresh replay

#### Scenario: Bound authentication refresh stays on the owner

- **GIVEN** a nonportable body is bound to account A
- **WHEN** account A reports a refreshable authentication failure before
  visible output
- **THEN** the proxy may refresh and replay once on account A
- **AND** it does not dispatch the retained body to account B

#### Scenario: HTTP bridge operation identity remains on its owner

- **GIVEN** an HTTP bridge retry retains a proxy-owned operation identity
- **AND** no explicit operation rebind has replaced that identity
- **WHEN** retry selection evaluates another account
- **THEN** the bridge requires the current operation owner

#### Scenario: Existing settlement ordering is unchanged

- **GIVEN** an API-key reservation requires settlement during the failed retry
- **WHEN** account health is updated
- **THEN** required settlement still completes before deferred health writes



### Requirement: Unanchored full resends recover from pre-visible quota rejection

The proxy MUST permit account failover for a Responses streaming request with no
previous-response or conversation anchor, no turn-state or input-file owner, and no
single-account routing after the selected account rejects the request for quota or rate
limits before any downstream event only when it can construct an account-neutral full resend.

The replay input MUST be produced by the shared response-owned-bookkeeping projection. The
projected request MUST pass the shared account-neutral fresh-replay validation and MUST retain
completed assistant output followed by fresh user input or an exact Codex host-generated
scheduled-task heartbeat. The proxy MUST preserve the requested
model, reasoning configuration, instructions, tools, and other account-neutral controls. It
MUST clear the failed attempt's soft payload-owner marker, exclude the rejected account, and
reallocate advisory prompt-cache affinity before reselection.

The proxy MUST NOT cross accounts for a request carrying a nonblank previous-response or
conversation anchor, a turn-state owner, an input-file owner, single-account routing, an
incomplete or non-neutral transcript, or any downstream-visible output. A non-quota failure
MUST retain its existing retry and ownership behavior.

#### Scenario: Full local transcript survives an exhausted sticky account

- **GIVEN** account A is selected for an unanchored prompt-cache-affine request
- **AND** the input contains a full self-contained transcript, response-owned reasoning state,
  retained assistant output, and fresh user input or a canonical scheduled-task heartbeat
- **AND** account B is eligible
- **WHEN** account A returns a quota rejection before any downstream event
- **THEN** the proxy removes response-owned reasoning state and item ids from the replay
- **AND** the proxy sends the account-neutral full resend on account B
- **AND** the response from account B is returned successfully

#### Scenario: HTTP and SSE quota rejection use the same recovery

- **WHEN** the pre-visible quota rejection arrives as either an HTTP error status or the first
  `response.failed` SSE event
- **THEN** the same account-neutral failover rules apply

#### Scenario: Scheduled heartbeat survives an exhausted sticky account

- **GIVEN** an unanchored full resend contains Codex host-generated scheduled-task heartbeats
- **AND** each heartbeat has the canonical `codex_app` automation shape and no upstream call id
- **WHEN** the selected account returns a pre-visible quota rejection
- **THEN** the proxy treats historical heartbeats as account-neutral host input
- **AND** the current heartbeat is retained as fresh input on the replay to another account
- **AND** malformed, namespaced differently, or call-id-bearing function outputs remain fail-closed

#### Scenario: Delta-shaped owner state stays fail-closed

- **GIVEN** an unanchored request whose input contains response-owned state and fresh user
  input but no retained prior assistant output
- **WHEN** the selected account returns a pre-visible quota rejection
- **THEN** the proxy surfaces the quota failure
- **AND** no part of the request is sent to another account

#### Scenario: Hard ownership stays fail-closed

- **GIVEN** a request carrying a previous-response, conversation, turn-state, or input-file
  owner, or constrained by single-account routing
- **WHEN** the owner returns a pre-visible quota rejection
- **THEN** the existing owner-bound behavior remains in force
- **AND** the proxy does not use this recovery to cross accounts


### Requirement: Observed HTTP response IDs publish same-process ownership before delivery

When an HTTP Responses attempt extracts a valid response ID from an actual upstream lifecycle event, it MUST publish that ID to the existing bounded process owner cache with the selected account and existing API-key/session scope before delivering the event that exposes the ID downstream. An immediate same-process follow-up referencing that ID MUST be able to resolve its known owner without waiting for the originating request-log write or originating stream completion. This readiness MUST apply from the first observed `response.created` carrying the ID; it MUST NOT promise that an unfinished response is already usable by the upstream provider.

The service MUST NOT publish a locally generated request/synthetic-error ID or a client-supplied anchor as new upstream ownership evidence. Cache misses MUST retain the existing durable request-log lookup and genuinely unknown-owner fail-closed behavior. Request-log persistence MUST remain under its existing detached task owner; this requirement MUST NOT introduce synchronous log barriers, a new registry or a cross-replica readiness guarantee.

Provenance for locally generated terminals MUST remain internal to the SSE carrier, preserve the exact serialized event bytes and existing retry markers, and survive reattachment of the parsed payload.

When normalization of an actual upstream error supplies a local response ID, that ID MUST remain ineligible for early ownership publication. The event MUST retain its upstream origin for timing observations.

#### Scenario: Follow-up starts after response-created delivery
- **GIVEN** two eligible accounts and an HTTP stream that has exposed its upstream response ID in `response.created` but has not completed
- **WHEN** a same-process HTTP follow-up references that ID
- **THEN** the known selected account is resolved before upstream dispatch
- **AND** ownership resolution does not wait for the first stream's terminal event or request-log write

#### Scenario: Terminal follow-up races detached persistence
- **GIVEN** a successful HTTP response whose request-log persistence is still pending
- **WHEN** the client submits an anchored follow-up immediately after terminal delivery or EOF
- **THEN** the existing process cache resolves the response owner in the existing caller scope
- **AND** the request is not rejected as unknown-owner solely because that write is pending

#### Scenario: Unobserved and out-of-scope IDs do not gain ownership
- **WHEN** a request references an ID not authoritatively observed for its allowed owner scope, including a local synthetic ID
- **THEN** no new cache entry is inferred from that request
- **AND** existing durable lookup, authorization and unknown-owner fail-closed rules apply
## MODIFIED Requirements

### Requirement: Observed HTTP response IDs publish same-process ownership before delivery

When an HTTP Responses attempt extracts a valid response ID from an actual upstream lifecycle event, it MUST publish that ID to the existing bounded process owner cache with the selected account and existing API-key/session scope before delivering the event that exposes the ID downstream. An immediate same-process follow-up referencing that ID MUST be able to resolve its known owner without waiting for the originating request-log write or originating stream completion. This readiness MUST apply from the first observed lifecycle event carrying the ID, including `response.created`, `response.queued`, and `response.in_progress`, whether delivered as SSE or adapted from a canonical background JSON acknowledgement; it MUST NOT promise that an unfinished response is already usable by the upstream provider.

The service MUST NOT publish a locally generated request/synthetic-error ID or a client-supplied anchor as new upstream ownership evidence. Cache misses MUST retain the existing durable request-log lookup and genuinely unknown-owner fail-closed behavior. Request-log persistence MUST remain under its existing detached task owner; this requirement MUST NOT introduce synchronous log barriers, a new registry or a cross-replica readiness guarantee.

Provenance for locally generated terminals MUST remain internal to the SSE carrier, preserve the exact serialized event bytes and existing retry markers, and survive reattachment of the parsed payload.

When normalization of an actual upstream error supplies a local response ID, that ID MUST remain ineligible for early ownership publication. The event MUST retain its upstream origin for timing observations.

#### Scenario: Follow-up starts after response-created delivery
- **GIVEN** two eligible accounts and an HTTP stream that has exposed its upstream response ID in `response.created` but has not completed
- **WHEN** a same-process HTTP follow-up references that ID
- **THEN** the known selected account is resolved before upstream dispatch
- **AND** ownership resolution does not wait for the first stream's terminal event or request-log write

#### Scenario: Terminal follow-up races detached persistence
- **GIVEN** a successful HTTP response whose request-log persistence is still pending
- **WHEN** the client submits an anchored follow-up immediately after terminal delivery or EOF
- **THEN** the existing process cache resolves the response owner in the existing caller scope
- **AND** the request is not rejected as unknown-owner solely because that write is pending

#### Scenario: Unobserved and out-of-scope IDs do not gain ownership
- **WHEN** a request references an ID not authoritatively observed for its allowed owner scope, including a local synthetic ID
- **THEN** no new cache entry is inferred from that request
- **AND** existing durable lookup, authorization and unknown-owner fail-closed rules apply

#### Scenario: Background acknowledgement precedes its log
- **GIVEN** two eligible accounts and a canonical HTTP background JSON acknowledgement with status `queued` or `in_progress`
- **WHEN** the same caller submits a continuation after receiving the acknowledgement while its log is pending
- **THEN** the known owner MUST resolve and receive that continuation without waiting for the originating log
- **AND** the acknowledgement MUST preserve its upstream ID and status

#### Scenario: In-progress lifecycle follows token delivery
- **GIVEN** an HTTP stream has delivered a text delta and first exposes its authoritative response ID in `response.in_progress`
- **WHEN** the event reaches the caller before stream completion
- **THEN** a same-process continuation MUST resolve the known owner before upstream dispatch

### Requirement: Explain continuity replay decisions without retaining request content

The proxy SHALL emit a versioned continuity replay decision at INFO level whenever the shared account-neutral payload classifier runs. The decision SHALL use a stable reason code from the classifier's actual validation path and include the request correlation hash and input count. It MUST NOT serialize request values, unknown field names, tool arguments, text, credentials or response tokens. Accepted and rejected outcomes SHALL use the same classifier implementation as routing.

#### Scenario: Unsupported control blocks transfer
- **WHEN** a complete resend fails reasoning-control validation
- **THEN** the decision identifies `reasoning_controls` rather than only reporting replay unavailable
- **AND** the rejected control's value is absent from the log

### Requirement: Explain durable full-resend proof gates

The HTTP bridge SHALL record whether a resend failed full-history recognition, lacked stored proof, mismatched its stored prefix, failed projection, or failed retained-output validation. The event SHALL correlate by request hash and include only counts and proof-presence booleans. It SHALL distinguish passed context proof from final payload portability acceptance.

#### Scenario: Retired anchor retains usable proof
- **WHEN** a resend matches retained input proof after anchor retirement
- **THEN** the proof event reports the actual prefix and retained-output outcome without requiring a live anchor

### Requirement: Retain the verified replay representation across live bridge reuse

When a complete resend has passed durable prefix, retained-output and whole-payload portability validation, the HTTP bridge MUST retain that same projected body as its fresh retry target after session-level anchor injection and input trimming. It MUST NOT replace the proven portable body with the raw body containing response-owned item IDs. This MUST NOT turn an unproven replay into a proven one or bypass file/turn-state/partial-output ownership constraints.

#### Scenario: Live owner rejects completed-tool continuation
- **GIVEN** the client resends complete history with response-owned bookkeeping IDs and a completed tool result
- **AND** the projected body passes the durable and portability gates
- **WHEN** a reused owner's socket rejects the next turn for quota before visible output
- **THEN** the fresh retry target uses the proven projected body
- **AND** durable-operation, client-turn-state and visible-output ownership gates remain independently enforced
