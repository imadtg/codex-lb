## ADDED Requirements

### Requirement: Projected model-transition recovery
The HTTP bridge SHALL accept validated consecutive plaintext developer instructions following a settled final answer and preceding the next user input as portable context. It SHALL retain the instructions in the projected request rather than requiring the original response owner solely because of their placement.

#### Scenario: Model switch adds multiple harness instructions
- **GIVEN** complete history contains the previous completed final answer followed by multiple plaintext developer messages and a new user message
- **WHEN** the original owner becomes unavailable
- **THEN** a compatible alternate receives the projected history and the following client request remains recoverable

### Requirement: Turn-state continuations have a durable execution fence
The HTTP bridge SHALL register a durable operation before dispatching a turn-state anchored continuation even when previous_response_id is absent. An explicit quota rejection before response creation SHALL use the verified portable projection for one fenced replacement.

#### Scenario: Turn token without previous response id
- **GIVEN** a client sends complete portable history with its established turn token and no previous_response_id
- **WHEN** the owner rejects quota before producing any response events
- **THEN** one alternate receives projected context without the old upstream turn token

#### Scenario: Recovery from an ordinary model fork
- **GIVEN** complete portable history and a fenced pre-created quota rejection on an ordinary internal model-change fork
- **WHEN** recovery publishes the client turn-token alias on the alternate lane
- **THEN** the ordinary fork's alias can transfer
- **AND** a competing live server-namespaced recovery lane remains protected

### Requirement: Model-isolated continuations preserve their current generation
The HTTP bridge SHALL publish the current logical generation atomically with successful owner-fenced completion and resolve subsequent full-history requests to that completed model-isolated conversation generation rather than an older incompatible history solely because the transport fork closed or the client omitted its turn token. This hint SHALL be scoped to the logical process/thread identity and API key, and SHALL NOT override explicit continuity aliases. Legacy rows without a published hint SHALL retain the existing alias and canonical-key lookup behavior.

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
