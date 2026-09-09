## ADDED Requirements

### Requirement: Portable local namespace tools preserve fresh replay eligibility
The proxy SHALL treat a namespace containing only validated function or custom tool declarations as account-neutral when its name is nonblank, its description is a string or absent, and its fields are known. It SHALL accept an optional boolean defer_loading on local tool declarations and an optional nonblank namespace on completed function/custom calls. All existing full-history, call/output pairing, ownership, and account-scoped state checks SHALL continue to apply.

#### Scenario: Exhausted owner with complete namespaced local tool history
- **WHEN** a verified full resend contains portable local namespace tools and its owner is unavailable
- **THEN** it remains eligible for the existing fresh replay account-switch path
- **AND** the alternate receives the complete call/output history

#### Scenario: Namespace contains unsupported or account-scoped tools
- **WHEN** a namespace contains a hosted tool, nested namespace, unknown field, or account-scoped state
- **THEN** the proxy rejects account-neutral fresh replay

### Requirement: Codex reasoning context controls remain portable
The replay validator SHALL accept the Codex reasoning context enum auto, current_turn, and all_turns (or null/absent), without treating the control itself as stored account state. Unknown context values SHALL remain ineligible.

#### Scenario: Full resend selects all-turn reasoning
- **WHEN** a complete portable request sets reasoning.context to all_turns
- **THEN** it remains eligible for fresh replay after owner loss

### Requirement: Client correlation identifiers do not pin payload replay
The validator SHALL accept nonblank string client_metadata values for session_id, thread_id, turn_id, parent_turn_id, and root_turn_id. It SHALL NOT treat these as proof of account ownership or permit arbitrary metadata fields, including opaque turn-state tokens.

#### Scenario: Codex correlation metadata survives a full replay
- **WHEN** an otherwise portable full resend carries the known client correlation identifiers
- **THEN** those identifiers alone do not prevent existing fresh replay recovery

### Requirement: Excluded hard owners terminate impossible recovery waits
A resolved hard sticky owner excluded by the current selection attempt SHALL return hard_affinity_owner_excluded without rebinding its mapping. Recovery wait logic SHALL NOT wait for this result. Existing bounded same-owner SSE retry SHALL remain available. An unexcluded temporarily unavailable hard owner SHALL retain its recovery wait.

#### Scenario: Created-only replay excludes legacy owner
- **WHEN** a legacy hard owner is excluded by the retry attempt
- **THEN** selection terminates with a distinct non-waitable result even if an alternate is healthy

### Requirement: Retained prefix comparison uses established forwarding normalization
Prefix verification SHALL preserve exact-match compatibility and SHALL also compare the existing namespace-stripped forwarding representation when the client supplies namespaced tool calls. It SHALL NOT ignore changes to arguments, call IDs, tool names, outputs, or other input fields. Stored fingerprints SHALL remain unchanged.

#### Scenario: Namespace stripped during prior dispatch
- **WHEN** prior dispatch stored a fingerprint after established namespace stripping and a full resend contains the same namespaced call history
- **THEN** comparison can recognize the exact dispatched representation without dropping any other fields

### Requirement: Poisoned transport abandonment preserves verified replay evidence
When abandoning a poisoned response/turn anchor without changing its account, the proxy SHALL retain the stored input count, fingerprint, and pending-call manifest for verification of a subsequent full-history request. Retention SHALL be fenced by the same owner epoch and expected anchors and SHALL NOT permit changing the account. Ordinary account rebinds SHALL continue to clear those fields. Retained proof SHALL NOT reintroduce the abandoned response anchor.

#### Scenario: Full history follows poisoned owner abandonment
- **WHEN** the owner is unavailable and the client supplies full history matching the retained proof after poison abandonment
- **THEN** the existing account-neutral recovery path can select an eligible replacement
- **AND** delta-only or modified histories remain rejected

### Requirement: Unanchored portable history can recover after legacy proof loss
When an unavailable durable account has no retained input proof, an explicitly unanchored request with no conversation, incoming turn-state, or account-owned file SHALL be eligible for the same validated portable-history projection used by soft-owner quota recovery. The request SHALL contain retained assistant output followed by fresh input and pass complete account-neutral validation. A failed prefix comparison when proof exists SHALL NOT use this exception. Account selection SHALL still enforce model eligibility, API-key scope and authorization.

#### Scenario: Old poison abandonment erased proof
- **WHEN** a complete unanchored portable request follows an old abandonment with missing input proof and its former owner cannot serve
- **THEN** the complete projected request can use a healthy eligible account without restoring the dead anchor

#### Scenario: Delta, altered known prefix, or explicit owner state
- **WHEN** a request lacks complete portable history, conflicts with existing proof, or supplies explicit account-owned continuity
- **THEN** this recovery exception is not available

### Requirement: Response-anchor retirement retains completed replay evidence
Clearing a rejected or eventless response anchor under the unchanged durable owner fence SHALL retain the completed input count, fingerprint and pending-call manifest. Those fields describe completed transcript evidence, not permission to reuse the rejected anchor. A new owner or an ordinary account rebind SHALL still clear or replace the proof according to its existing contract. Denied-anchor alias removal and concurrent-anchor/epoch fencing SHALL remain unchanged.

#### Scenario: Explicit rejection precedes owner loss
- **WHEN** a response anchor is rejected and retired before the owner becomes unavailable
- **THEN** a later complete client resend can be checked against the retained fingerprint and manifest
- **AND** a changed prefix, missing tool output or stale owner mutation remains rejected

### Requirement: Local namespace parameter schemas are declarations
Account-neutral validation SHALL treat a validated namespace child's function parameters as a JSON schema, including properties named file_id or image_url, rather than as supplied account-owned resources. Unknown namespace children and actual resource references outside parameter schemas SHALL remain rejected.

#### Scenario: Codex collaboration namespace declares an image URL argument
- **WHEN** a local namespace function parameter schema includes image_url as a property name
- **THEN** that schema alone does not prevent portable replay

### Requirement: Codex web-search access flags are portable controls
The web_search tool declaration SHALL accept boolean external_web_access and indexed_web_access without treating either as account-owned state. Nonboolean values and unknown options SHALL remain rejected.

#### Scenario: Cached web search in a complete resend
- **WHEN** Codex includes external_web_access=false in its web_search declaration
- **THEN** that option alone does not block account-neutral replay

### Requirement: Explicit live quota rejection uses fenced full-history recovery
An anchored operation rejected explicitly for quota before any response output SHALL be eligible for one server-owned account-neutral recovery when its complete history is durably proven and its operation is owner-fenced. Recovery SHALL preserve the operation identity, exclude the rejected account, and re-register ownership before replacement dispatch. Missing proof, account-owned resources, prior replay, or visible output SHALL NOT gain permission to switch accounts.

#### Scenario: Live owner rejects a proven continuation for quota
- **WHEN** the live owner explicitly rejects a durably proven portable continuation before response creation and another eligible account exists
- **THEN** the proxy recovers through its fenced operation rebind path without requiring another client request
- **AND** the replacement receives the complete tool history and the original operation identity

### Requirement: Unanchored plaintext tool history can fail over after explicit rejection
For a client-unanchored request without mandatory account, file, or turn-state ownership, the proxy SHALL allow explicit pre-visible quota rejection to release a soft payload owner when removing only response-item IDs makes the entire request account-neutral. This normalization SHALL NOT omit history items or supply proof for an anchored continuation. All tool calls SHALL have matching outputs and the original request SHALL include a user message.

#### Scenario: Tool-only assistant turn followed by its result
- **WHEN** a client-unanchored plaintext history includes user input and a complete tool-call/result exchange with response-item IDs and its soft owner rejects it for quota before visible output
- **THEN** an eligible alternate receives the same history with only response-item IDs removed
- **AND** explicit ownership, incomplete tool exchanges and opaque context remain ineligible
