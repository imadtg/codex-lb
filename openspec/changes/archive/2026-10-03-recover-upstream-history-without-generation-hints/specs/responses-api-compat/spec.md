## ADDED Requirements

### Requirement: Portable history recovery does not require generation hints
For an unanchored full-history request whose selected branch cannot prove the supplied context, the HTTP bridge SHALL support a unique matching completed history proof stored by the unmodified base in the caller's API-key scope without requiring a logical-generation hint. It SHALL validate prefix identity and retained output/tool settlement before authorizing projected fresh execution. A content match SHALL NOT authorize reuse of the matched row's account-owned upstream response, turn token, or client aliases. Explicit client continuity anchors SHALL retain their existing ownership semantics.

#### Scenario: Unmodified producer and patched continuation
- **GIVEN** compacted context completed on an isolated model branch using the unmodified base and the service is replaced against the same persistent database
- **WHEN** the patched service receives the matching full history without a turn token or response id
- **THEN** it projects the complete supplied context without requiring new branch metadata
- **AND** it preserves durable execution protection before dispatch

#### Scenario: Return to the unmodified base
- **GIVEN** the patched service completed that recovery and returned its ordinary continuity token
- **WHEN** the service is replaced by the unmodified base and the client sends its standard token with the next history
- **THEN** the unmodified base continues the conversation without state conversion

#### Scenario: Explicit ownership and invalid context
- **GIVEN** an explicit continuity anchor or a mismatched prefix, missing tool result, or account-bound file
- **WHEN** the request is evaluated for history-proof discovery
- **THEN** content similarity does not bypass ownership or retained-context validation

#### Scenario: Ambiguous proof identity
- **GIVEN** multiple completed rows qualify for the same history proof in the caller's scope
- **WHEN** no exact continuity anchor disambiguates them
- **THEN** the service does not arbitrarily select an upstream owner or discard an execution fence

#### Scenario: Unrelated retained branches
- **GIVEN** more than 256 unrelated completed branches exist in the caller's scope
- **WHEN** exactly one completed proof qualifies for the supplied history
- **THEN** unrelated rows do not prevent discovering that proof

#### Scenario: Interrupted recovery survives restart
- **GIVEN** projected recovery emitted partial output and disconnected before completion
- **WHEN** the process restarts and receives identical history with a newly derived prompt-cache key
- **THEN** its durable operation fence replays the recorded failure or refuses unresolved execution without another dispatch
- **AND** explicit cache keys, different client scopes, different API-key scopes, and changed request content retain distinct execution identities

## MODIFIED Requirements

### Requirement: Model-isolated continuations preserve their current generation
The HTTP bridge SHALL publish the current logical generation atomically with successful owner-fenced completion and resolve subsequent full-history requests to that completed model-isolated conversation generation rather than an older incompatible history solely because the transport fork closed or the client omitted its turn token. This hint SHALL be scoped to the logical process/thread identity and API key, and SHALL NOT override explicit continuity aliases. Legacy rows without a published hint SHALL retain existing exact alias semantics and SHALL support validated portable history recovery without requiring the hint.

#### Scenario: Compaction then model change then retry
- **GIVEN** compacted history completes on an isolated model-transition session
- **WHEN** that session closes and the client retries its current full history without a turn token
- **THEN** recovery uses the matching generation's history proof and does not compare it against the predecessor's longer input

#### Scenario: Explicit older anchors remain authoritative
- **GIVEN** a newer completed model fork has published its logical generation
- **WHEN** the client explicitly references the predecessor's response or turn token
- **THEN** the explicit alias retains its original session meaning

#### Scenario: Rejected completion leaves generation unchanged
- **GIVEN** a completed logical generation is registered
- **WHEN** another completion is rejected by an ownership fence or protected response alias
- **THEN** the existing logical generation and rejected session's completion proof remain unchanged
