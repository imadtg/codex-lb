## ADDED Requirements

### Requirement: Recovery ports retain the fork's projectable context

Verified full-resend recovery SHALL retain projectable reasoning, compaction, search records, tool call/output pairs and native agent-message content in order. It MAY unlink source item IDs. Agent input SHALL NOT replace missing prior output or incomplete pending-tool settlement. Recovery SHALL preserve operation admission, visible-output and unknown-execution fences. Resource-bound bodies SHALL remain on their required account. Equivalent HTTP bridge and direct WebSocket recovery SHALL respect the same context retention and settlement-before-health invariants.

#### Scenario: Full resend switches accounts without context loss

- **GIVEN** a verified full resend containing retained ciphertext and a complete local tool history
- **WHEN** the original account reports usage exhaustion before visible output
- **THEN** an eligible alternate receives the complete projectable history without source-owned anchors
- **AND** account health writes occur only after usage reservation settlement
