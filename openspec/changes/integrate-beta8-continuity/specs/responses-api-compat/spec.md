## ADDED Requirements

### Requirement: Fenced quota rejection handoff preserves client history
The HTTP bridge SHALL permit one account-neutral replacement after an explicit pre-created quota rejection only when complete portable context is proven, the durable operation is fenced, no other request is pending, and no account-owned file is present. It SHALL retain the original client-history fingerprint when the outgoing projection removes response bookkeeping.

#### Scenario: Alternate account has quota
- **WHEN** a completed tool turn is followed by a full-history resend and the owner explicitly rejects quota before creating a response
- **THEN** a compatible alternate receives the complete portable input without the old upstream anchor or turn token, and a subsequent full-history follow-up remains recoverable

#### Scenario: Accepted output or incomplete history
- **WHEN** a response has been created or the supplied tool history lacks required output
- **THEN** this quota-rejection handoff path does not dispatch the request on another account

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
