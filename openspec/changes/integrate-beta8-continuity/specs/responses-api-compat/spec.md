## ADDED Requirements

### Requirement: Exhausted selection preserves definitive quota rejection
When a pre-created retry follows an explicit quota rejection and account selection fails with `no_accounts` before a replacement dispatch, the HTTP bridge SHALL preserve the provider's quota terminal instead of synthesizing a transport-incomplete failure. This SHALL NOT permit unproven history to cross accounts or suppress an ambiguous transport failure.

#### Scenario: Changed history cannot leave an exhausted owner
- **GIVEN** a full resend differs from its completed historical prefix and retains account-bound response metadata
- **WHEN** its owner rejects it with quota exhaustion before response creation and mandatory-owner retry selection finds no account
- **THEN** the client receives the original quota error and no alternate receives the request

### Requirement: Fenced quota rejection handoff preserves client history
The HTTP bridge SHALL permit one account-neutral replacement after an explicit pre-created quota rejection only when complete portable context is proven, the durable operation is fenced, no other request is pending, and no account-owned file is present. It SHALL retain the original client-history fingerprint when the outgoing projection removes response bookkeeping.

#### Scenario: Alternate account has quota
- **WHEN** a completed tool turn is followed by a full-history resend and the owner explicitly rejects quota before creating a response
- **THEN** a compatible alternate receives the complete portable input without the old upstream anchor or turn token, and a subsequent full-history follow-up remains recoverable

#### Scenario: Accepted output or incomplete history
- **WHEN** a response has been created or the supplied tool history lacks required output
- **THEN** this quota-rejection handoff path does not dispatch the request on another account

#### Scenario: Replacement rejects quota before creation
- **WHEN** a recovery lane temporarily claims the client turn alias and definitively rejects quota before creating a response
- **THEN** the proxy SHALL restore the previous alias through the existing owner-fenced rollback, preserving the predecessor's proof without transferring response ownership
- **AND** an identical full-history retry SHALL remain recoverable when another compatible account becomes available

#### Scenario: Replacement outcome is ambiguous or accepted
- **WHEN** the replacement disconnects without definitive rejection or has already created a response
- **THEN** the proxy SHALL NOT restore the predecessor alias through the quota-rejection rollback

### Requirement: Portable Codex host inputs retain strict boundaries
The account-neutral proof SHALL recognize validated plaintext agent deliveries, local namespace tool declarations, host automation heartbeats, and fingerprinted historical developer context. Encrypted agent content, missing tool settlement, account-owned files, and unexplained prefix changes SHALL NOT satisfy this proof. Agent deliveries SHALL NOT themselves prove retention of upstream output or settle outstanding tool calls.

#### Scenario: Agent delivery follows a settled tool batch
- **WHEN** full history retains the proven prefix and completed tool batch followed by a valid plaintext agent delivery
- **THEN** the delivery is treated as external follow-up input and does not prevent an otherwise eligible quota handoff

### Requirement: Replay diagnostics preserve bounded request evidence
Continuity failures SHALL include bounded content-free proof and retry evidence scoped to the logical request. Upstream typed rejection diagnostics SHALL remain available.

#### Scenario: A child startup task observes a rejection
- **WHEN** the parent returns an owner-unavailable error after a startup child observed a proof refusal
- **THEN** the final failure retains scoped reason evidence without raw input, account credentials, or opaque identifiers

## MODIFIED Requirements

### Requirement: A stuck eventless HTTP bridge reattach invalidates its durable anchor for full-resend clients

When a proxy-injected durable `previous_response_id` anchor causes an HTTP bridge `response.create` to reach the eventless client-safe timeout (`missing_response_created_timeout`) without producing `response.created` or any other response event, and the client's own incoming payload for that request already looked like a full conversation resend, the proxy MUST clear that durable session's stored response anchor (`latest_response_id`) while preserving the completed input count, fingerprint, and pending-tool-call manifest before releasing durable ownership, fenced to the session's current owner epoch. A client-supplied `previous_response_id` MUST NOT be cleared by this path. A proxy-injected anchor on a payload that did not look like a full resend (a genuine delta-only continuation) MUST NOT be cleared by this path, because the client has no other way to convey prior conversation state once the anchor is gone. The durable session's turn-state and identity MUST remain intact so a later request can still reattach without the stale anchor.

#### Scenario: Full-resend proxy-injected anchor times out and is cleared

- **GIVEN** a durable HTTP bridge session has a stored `latest_response_id`
- **AND** a fresh reattach injects that response id as `previous_response_id` because the client sent none
- **AND** the client's incoming payload already looked like a full conversation resend
- **WHEN** the resulting `response.create` reaches the eventless client-safe deadline with no `response.created` or other response event
- **THEN** the terminal `missing_response_created_timeout` failure is delivered as before
- **AND** the durable session's `latest_response_id` is cleared under the current owner epoch while completed input proof and its tool-call manifest are retained
- **AND** the durable session's turn-state alias remains available for reattachment

#### Scenario: Next reattach takes the fresh no-anchor path

- **GIVEN** a durable session's anchor was cleared after a stuck eventless timeout on a full-resend payload
- **WHEN** a later request reattaches to the same durable session with no `previous_response_id`
- **THEN** the proxy does not inject a `previous_response_id` anchor for that request
- **AND** the request proceeds on the existing unanchored full-resend/fresh path instead of repeating the cleared anchor

#### Scenario: Delta-only proxy-injected anchor is left intact

- **GIVEN** a fresh reattach injects a durable `previous_response_id` anchor because the client sent none
- **AND** the client's incoming payload did not look like a full conversation resend
- **WHEN** the resulting `response.create` reaches the eventless client-safe deadline with no `response.created` or other response event
- **THEN** the terminal `missing_response_created_timeout` failure is delivered as before
- **AND** the durable session's `latest_response_id` is not cleared
- **AND** the next reattach on that session still injects the same anchor, preserving the client's only way to convey prior context

#### Scenario: Client-supplied anchor is left untouched

- **GIVEN** a request supplied its own `previous_response_id` rather than receiving a proxy-injected one
- **WHEN** its `response.create` reaches the eventless client-safe timeout
- **THEN** the durable session's `latest_response_id` is not cleared
- **AND** later requests may still resolve that alias per existing continuity rules

#### Scenario: Fenced anchor-clear loses to a newer owner

- **GIVEN** a durable session's owner epoch has advanced past the retiring session's epoch before the anchor-clear write executes
- **WHEN** the stuck-timeout handling attempts to clear the anchor
- **THEN** the write is a no-op
- **AND** the newer owner's durable state is left untouched

### Requirement: Verified full resend can recover from selection-time owner loss

For selection-time owner loss, an HTTP bridge request MAY move from an unavailable continuity owner to another account only after a typed pre-visible `continuity_owner_unavailable` account-selection result, which the HTTP bridge maps to `previous_response_owner_unavailable`, and positive durable proof that the request contains the complete retained input history. A missing durable owner is not a selector result and MUST fail closed without replay. The durable row MUST provide a positive input-item count and full fingerprint, and the corresponding prefix of the incoming list-shaped input MUST match both before replay projection. This comparison MAY apply the existing forwarding normalization that removes tool-call namespaces; all other fields MUST remain part of the fingerprint.

After the raw prefix proof, the service MUST construct a deterministic plaintext projection by omitting `reasoning`, `web_search_call`, `tool_search_call`, and `tool_search_output` items and removing upstream `id` fields from every retained input item. Retained message metadata MUST use validated field types. Fingerprinted historical developer messages MAY retain a nonblank `turn_id` and validated `content_item_kinds`; plaintext agent deliveries and host heartbeat metadata MUST satisfy their explicit portability validators. The projected suffix after the projected prefix MUST contain a completed assistant `output_text` or `refusal` boundary with nonblank content followed by nonblank fresh text or valid fresh file/image input. The suffix MAY contain multiple intervening turns only when every non-final user-input sequence is followed by another completed assistant boundary and the final sequence ends in fresh input. Direct intrinsic calls MAY precede an assistant boundary only when terminal completed or failed outputs settle every represented call in order. A call at the end of the verified raw prefix MAY be settled by its matching output at the start of the suffix. A direct-call/output sequence alone MUST NOT prove completeness unless it exactly settles the persisted response-bound pending-tool-call manifest; a call absent from that manifest or missing its matching result MUST fail closed. A matching prefix followed only by new user input, empty content, tool-call-only output without exact manifest proof, in-progress or partial retained output, duplicate, unmatched, or unresolved calls, or misordered call output MUST fail closed.

The service MUST validate the complete projected request after removing `previous_response_id`; it MUST reject nonblank conversation or prompt handles, remaining encrypted content, compaction, opaque account-scoped file/container/vector handles, nonportable file schemes, hosted, MCP, program-mediated, or unknown call or tool-choice state, unknown top-level fields, unknown or malformed top-level reasoning configuration, malformed message/content shapes, and tool outputs without exactly one matching intrinsic call. Assistant messages MUST contain only supported output parts, while user, system, and developer messages MUST contain only supported input parts. Inline data images and HTTP(S) file/image content MAY remain eligible. Eligible declared tools, tool choices, and retained direct calls MUST be shape-validated, account-neutral, and self-contained. Web-search filters, context size, and approximate location MUST use only the recognized nested fields and value types. An apply-patch call MUST use exactly one representation: a recognized structured `operation` with its exact discriminated fields, a nonblank legacy `patch`, or a nonblank legacy `input`.

For an eligible replay, the service MUST remove `previous_response_id`, strip every downstream session/turn alias, clear hard affinity, exclude the unavailable owner, prevent initial bridge-owner forwarding, and submit the complete projected request through a fresh server-namespaced recovery lane. It MUST NOT replay after downstream-visible output. Selection policy conflicts, authentication/connection failures after selection, incomplete history, or any unsafe request state MUST remain fail-closed.

#### Scenario: Client-supplied full resend moves from A to B

- **GIVEN** account A owns a completed previous response and its durable row stores the completed input count and fingerprint
- **AND** a follow-up supplies that previous response plus an account-neutral full resend whose retained prefix matches both values
- **WHEN** required-owner selection returns typed `continuity_owner_unavailable` before output
- **THEN** the bridge removes the previous-response anchor and all stale affinity headers
- **AND** excludes account A and submits the complete fresh request once on account B
- **AND** the next turn for the recovered task remains on account B

#### Scenario: Proxy-injected anchor protects an equivalent full resend

- **GIVEN** a hard durable alias resolves a completed response and the incoming full resend matches its retained count and fingerprint
- **AND** the proxy injects that response as the reattach anchor
- **WHEN** required-owner selection returns typed `continuity_owner_unavailable` before output
- **THEN** the same fresh-replay rules apply after the injected anchor is removed

#### Scenario: Verified resend contains owner-bound reasoning

- **GIVEN** a verified full resend contains encrypted reasoning, server-assigned item IDs, and completed web or tool-search bookkeeping
- **AND** its retained assistant and direct-tool content is otherwise complete and portable
- **WHEN** required-owner selection returns typed `continuity_owner_unavailable` before output
- **THEN** the bridge omits the reasoning and search bookkeeping and strips upstream item identities
- **AND** no encrypted content or upstream item identity is sent to account B
- **AND** the validated plaintext projection is submitted once on account B

#### Scenario: Retained request contains account-scoped state

- **GIVEN** a full resend contains a conversation or prompt handle, compaction, encrypted content outside an omitted reasoning item, an opaque account-scoped file/container/vector handle, a nonportable file scheme, hosted or MCP call or tool-choice state, an unknown call type, or an unmatched tool output
- **WHEN** its required owner is unavailable
- **THEN** the request fails with `previous_response_owner_unavailable`
- **AND** none of that state is sent to another account

#### Scenario: Request shape is not completely understood

- **GIVEN** a purported full resend contains an unknown top-level field or malformed/unknown message content
- **WHEN** its required owner is unavailable
- **THEN** replay eligibility fails closed
- **AND** the service does not infer portability from the retained fingerprint alone

#### Scenario: Matching input prefix omits the prior response output

- **GIVEN** the incoming input prefix matches the durable count and fingerprint
- **AND** the suffix contains only a new user message, a direct-call/output sequence without a later completed assistant boundary or exact persisted-manifest proof, partial retained output, or unresolved direct calls
- **WHEN** the required owner is unavailable
- **THEN** replay eligibility fails closed with `previous_response_owner_unavailable`
- **AND** the proxy does not drop the previous-response anchor or send the incomplete transcript to another account

#### Scenario: Owner was selected before a later failure

- **GIVEN** the required owner was selected successfully
- **WHEN** refresh, authentication, WebSocket connection, transport, or timeout fails before output
- **THEN** the request keeps that ordinary failure classification
- **AND** the service does not activate cross-account full-resend recovery

#### Scenario: Durable continuity row has no account owner

- **GIVEN** a durable continuity row proves retained input but has no account owner
- **WHEN** the request is evaluated before account selection
- **THEN** the bridge returns `previous_response_owner_unavailable`
- **AND** it does not treat the missing owner as a typed selector miss or replay on another account

#### Scenario: Failure occurs after visible output

- **WHEN** any part of a response has become downstream-visible
- **THEN** the service does not replay the request on another account
- **AND** it terminates through the existing partial-output failure contract

### Requirement: Verified replay continuity remains task-specific and fenced

A recovery lane MUST use a server-namespaced key within the existing durable `internal_unanchored_parallel` kind. Once it registers a turn-state or previous-response alias, that specific alias MUST resolve the recovery lane ahead of a conflicting broad session-header alias, while the shared session-header alias remains unchanged for sibling tasks. Conflicting specific aliases MUST still fail with `continuity_owner_conflict`, and unrelated internal lanes MUST NOT receive recovery precedence.

Alias ownership changes MUST be atomic. A recovery lane MAY replace only an alias owned by a documented prompt-cache, session-header, or turn-state predecessor, or by an ownerless or released/null-lease or lease-expired prior recovery lane. It MUST NOT replace an actively leased recovery lane. An ordinary or stale session MUST NOT replace a recovery alias. Owner-epoch fencing MUST invalidate the fenced local session; rejection because an alias is protected MUST remove only the rejected alias and MUST preserve sibling aliases and the rest of the session.

A recovery lane MUST acquire and renew fenced durable ownership before publishing continuity or dispatching a request. Immediately before upstream dispatch, the lane MUST atomically publish the incoming turn-state alias and its latest-turn state. If cancellation occurs after that commit but before dispatch may have started, cleanup MUST roll back the provisional alias and latest-turn state before reporting cancellation. Rollback MAY restore the predecessor only when its owner epoch and account still match the registration receipt; otherwise rollback MUST remove only the provisional alias. Once dispatch may have started, an ambiguous or accepted outcome MUST keep the alias on the recovery lane. A definitive quota rejection before response creation MAY roll back the provisional alias through the same owner-fenced receipt, only while no other request is pending. A closed predecessor with a retired response anchor MAY enter the existing recovery lane on a later full resend only when retained portable context is positively proven; missing or mismatched proof MUST NOT qualify. A completed response MUST NOT be advertised downstream as successful when its required durable response-alias publication fails.

#### Scenario: Recovered task and sibling share a session header

- **GIVEN** a recovered task registered a specific alias on account B
- **AND** its shared session header still resolves a sibling lane on account A
- **WHEN** the recovered task sends both aliases
- **THEN** durable lookup resolves account B's recovery lane
- **AND** session-header-only sibling traffic continues to resolve account A

#### Scenario: Specific recovery aliases conflict

- **GIVEN** a recovery turn-state alias and previous-response alias resolve different durable sessions
- **WHEN** both are supplied
- **THEN** the request fails with `continuity_owner_conflict`
- **AND** broad-alias precedence does not hide the conflict

#### Scenario: Stale session attempts to reclaim a recovery alias

- **GIVEN** a recovery lane owns a specific durable alias
- **WHEN** an ordinary or stale predecessor session registers the same alias
- **THEN** the durable write reports the alias as protected
- **AND** the recovery alias remains unchanged
- **AND** unrelated aliases on the rejected session remain usable

#### Scenario: Recovery lane rebinds a documented predecessor alias

- **GIVEN** a prompt-cache, session-header, turn-state, or ownerless/lease-expired prior recovery lane owns an alias for the same recovered task
- **WHEN** the current recovery lane registers that alias while its owner epoch is valid
- **THEN** the conditional durable write rebinds the alias atomically

#### Scenario: Active recovery lane protects its alias

- **GIVEN** an actively leased recovery lane owns a specific alias
- **WHEN** another recovery lane attempts to register that alias
- **THEN** the durable write reports the alias as protected
- **AND** the active recovery owner and alias remain unchanged

#### Scenario: Cancellation occurs after alias commit and before dispatch

- **GIVEN** a recovery lane atomically committed the incoming turn-state alias immediately before dispatch
- **WHEN** its task is cancelled before upstream send may have started
- **THEN** cleanup completes the fenced rollback before surfacing cancellation
- **AND** the predecessor is restored only if its captured epoch and account are unchanged
- **AND** otherwise only the provisional recovery alias is removed
- **AND** no upstream request is sent

#### Scenario: Cancellation occurs after dispatch may have started

- **GIVEN** a recovery lane committed the incoming turn-state alias
- **WHEN** cancellation occurs after upstream send may have started
- **THEN** the recovery alias remains authoritative
- **AND** the ambiguous socket retires before an admitted waiter can reconnect or submit on it

#### Scenario: Completed response alias cannot be persisted

- **WHEN** a recovery response reaches `response.completed`
- **AND** fenced durable publication of its response alias fails
- **THEN** downstream does not receive a successful completion for that response
- **AND** the recovery lane retires fail-closed
