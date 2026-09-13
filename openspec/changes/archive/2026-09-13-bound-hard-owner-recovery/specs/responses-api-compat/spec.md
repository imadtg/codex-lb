## ADDED Requirements

### Requirement: Hard-owner selection recovery is bounded
An HTTP stream whose hard-affinity owner is unavailable SHALL allow one brief
selection recovery wait and reselect before surfacing the existing selection
failure. Continued hard-owner unavailability SHALL NOT repeatedly replenish that
wait until the overall inference budget expires. The rule SHALL be independent
of a recent WebSocket transport failure. A recovering owner SHALL remain eligible;
an alternate account SHALL NOT receive account-bound input.

#### Scenario: Unavailable hard owner
- **WHEN** required hard-affinity selection remains unavailable after its brief recovery wait
- **THEN** the stream terminates with its existing selection error without alternate dispatch

#### Scenario: Owner recovers during the wait
- **WHEN** the owner becomes eligible during that recovery wait
- **THEN** the next selection can dispatch on that owner

### Requirement: Commentary does not obscure exact tool settlement
Account-neutral replay proof SHALL permit a retained assistant commentary
message immediately before an exact persisted tool-call batch. The tool calls
and outputs SHALL still exactly match the persisted manifest. Commentary with
opaque content and incomplete tool settlement SHALL remain ineligible.

#### Scenario: Commentary precedes a settled tool batch
- **WHEN** retained plaintext commentary precedes every persisted call and its matching output
- **THEN** a pre-created quota rejection may hand the full account-neutral history to another eligible account

#### Scenario: Commentary precedes an incomplete or opaque batch
- **WHEN** any persisted output is missing or the commentary contains opaque content
- **THEN** quota handoff remains unavailable
