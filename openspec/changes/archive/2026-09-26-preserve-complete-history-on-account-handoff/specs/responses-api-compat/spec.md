## MODIFIED Requirements

### Requirement: Responses-Lite replay proof tolerates only verified developer interleaving

When a fresh durable HTTP bridge classifies a client-unanchored Responses-Lite
full resend whose `additional_tools` bundle preserves developer messages inline,
the replay proof MUST tolerate a developer message only in the historical and
fresh positions defined below. Every other developer position or shape MUST
remain fail-closed.

A tolerated fresh developer message MUST have `type` omitted or equal to `message`,
MUST have role `developer`, MUST have no phase, MUST have no status or a
`completed` status, MUST contain exactly one self-contained `input_text` content
part, and MUST contain no unknown or account-scoped fields. The terminal
user-then-developer shape MUST have no non-empty response-owned ID and MUST
contain exact account-neutral metadata with one nonblank `turn_id`. The
completed-final-answer, developer-before-user shape MAY have a top-level
response-owned ID and MAY lack metadata, but any present metadata MUST be
account-neutral. Explicit null or malformed item types MUST fail closed.

Classification MUST retain response-owned developer-message ID evidence until
these checks have completed, even when other response-owned IDs are projected
out. It MUST retain developer-role items before applying projection rules that
normally omit their declared item type, so a malformed developer item cannot
disappear before validation. A canonical Lite-prefix developer instruction MAY
appear immediately after the `additional_tools` bundle when it passes the same
account-neutral item checks as historical interleaving and has no response-owned
ID. A developer message in the stored prefix outside that canonical position or
the verified pending-call/matching-output interleave MUST fail closed. Non-Lite
`input` or `messages` forms whose instruction-role messages are normalized into
top-level `instructions` remain outside this requirement.

#### Scenario: Canonical Responses-Lite prefix remains transparent

- **GIVEN** a fingerprint-verified stored prefix begins with an `additional_tools` bundle
- **AND** a valid account-neutral developer instruction appears immediately after that bundle
- **WHEN** exact manifest or retained-output replay proof validates the stored prefix
- **THEN** the canonical developer instruction is transparent
- **AND** the original full input remains eligible for account-neutral replay

#### Scenario: Verified historical Responses-Lite developer message is transparent

- **GIVEN** a Responses-Lite input contains an `additional_tools` bundle
- **AND** its fingerprint-verified stored prefix contains a supported direct call
- **AND** a valid developer message appears before that call's matching output
- **AND** the fresh suffix exactly settles the durable pending-tool manifest
- **WHEN** the HTTP bridge opens a replacement session on the durable owner
- **THEN** it sends the original full input without injecting `previous_response_id`
- **AND** it sends the request once

#### Scenario: Other historical messages remain fail-closed

- **GIVEN** a supported direct call is pending in the verified stored prefix
- **WHEN** a user, assistant, system, malformed developer, or response-owned message appears before its output
- **THEN** exact manifest proof fails

#### Scenario: Other stored developer positions remain fail-closed

- **GIVEN** a fingerprint-verified stored prefix has no pending direct call
- **WHEN** a developer message appears outside the canonical adjacent Lite-prefix position
- **OR** the adjacent message has a response-owned ID
- **THEN** exact manifest and retained-output proofs fail

#### Scenario: Projection-omitted developer type remains visible to validation

- **GIVEN** a developer-role item declares a type normally omitted by replay projection
- **WHEN** account-neutral replay classification projects the full resend
- **THEN** the malformed developer item remains visible to replay proof
- **AND** replay classification fails closed

#### Scenario: Historical output remains mandatory

- **GIVEN** a valid developer message follows a supported historical call
- **WHEN** the matching output is missing or has another call ID or type
- **THEN** exact manifest proof fails

#### Scenario: Historical developer interleaving is bounded to one call and one message

- **GIVEN** a fingerprint-verified stored prefix opens a pending direct-call window
- **WHEN** that window holds more than one outstanding call at any point before the developer message
- **OR** a further call opens in that window after it has consumed a developer message
- **OR** a second developer message appears while the same window is still open
- **THEN** exact manifest proof fails
- **AND** a later window that holds exactly one outstanding call may still interleave one developer message

#### Scenario: Fresh developer suffix bounds are measured on the projected input

- **GIVEN** account-neutral replay classification projects the full resend
- **WHEN** the projection omits reasoning or completed bookkeeping items from the fresh suffix
- **THEN** the fresh developer suffix and terminality bounds are evaluated on the projected positions
- **AND** the accepted width is limited to shapes whose projected suffix satisfies those bounds

#### Scenario: Bounded fresh custom-tool developer interleave is transparent

- **GIVEN** the fingerprint-verified stored prefix is followed by a fresh suffix
- **AND** the durable pending-tool manifest contains exactly one `custom_tool_call`
- **WHEN** the entire suffix is exactly that custom call, one valid developer message, and its matching custom-tool output
- **THEN** exact manifest proof passes
- **AND** the original full input is sent once without injecting `previous_response_id`

#### Scenario: Other fresh tool-loop developer positions remain fail-closed

- **GIVEN** a durable pending-tool manifest
- **WHEN** a fresh developer message is used with a function or apply-patch call, appears in a parallel batch, is duplicated, lacks exact metadata, contains malformed or account-scoped content, or has leading or trailing suffix items
- **THEN** exact manifest proof fails

#### Scenario: Bounded retained-output developer follow-up is transparent

- **GIVEN** the fingerprint-verified stored prefix is followed by a completed assistant `final_answer`
- **AND** exactly one explicit user message follows that retained output
- **WHEN** one valid developer message is the terminal suffix item
- **THEN** retained-output proof passes
- **AND** the original full input is sent once without injecting `previous_response_id`

#### Scenario: Unproven retained-output developer follow-up remains fail-closed

- **GIVEN** a retained-output full resend
- **WHEN** the latest assistant output is not `final_answer`, the developer message violates both the terminal follow-up and single-user preface bounds, the fresh input is raw or contains multiple user items, the developer metadata or content is not account-neutral, or the stored prefix contains historical developer interleaving
- **THEN** retained-output proof fails

#### Scenario: Bounded developer preface before fresh user survives handoff
- **GIVEN** a fingerprint-verified stored prefix is followed by a completed assistant `final_answer`
- **WHEN** one valid developer instruction with a top-level item ID precedes exactly one fresh user message
- **THEN** retained-output proof passes
- **AND** cross-account replay retains the instruction content while unlinking only its top-level ID

#### Scenario: Incomplete answer before developer preface remains owner-bound
- **WHEN** the assistant response before a developer preface is not a completed `final_answer`
- **THEN** retained-output proof fails even if a fresh user message follows

## ADDED Requirements

### Requirement: Exact tool-manifest proof preserves validated response context

When a fingerprint-verified full resend exactly settles the persisted response-bound tool-call manifest, the proof SHALL allow validated reasoning, compaction, and search records outside the call/output batch without treating those records as calls or outputs. The replayed request SHALL retain these context records byte-identically except for their top-level response-owned IDs. Invalid or unfinished context records and missing or mismatched tool outputs SHALL remain ineligible for handoff.

#### Scenario: Encrypted reasoning precedes a settled tool batch
- **GIVEN** the durable prior response records exactly one pending custom tool call
- **AND** the client resends encrypted reasoning, completed commentary, that call and its matching output, then a fresh user message
- **WHEN** the hard owner is unavailable and another ChatGPT account is eligible
- **THEN** the proxy replays the complete context on the alternate account once
- **AND** the reasoning ciphertext, commentary, call, output, and user message retain their content

#### Scenario: Incomplete tool batch remains owner-bound
- **GIVEN** retained reasoning and commentary accompany a persisted pending tool call
- **WHEN** its matching output is missing or the reasoning record is invalid
- **THEN** the proxy does not dispatch the continuation on another account

### Requirement: Pre-visible account rejection does not move unsettled history

When an ordinary HTTP response attempt is rejected for quota or a permanent account-local error before output, a soft-owner handoff SHALL revalidate the candidate full input after removing only top-level response-owned item IDs. The handoff SHALL occur only when the resulting request is account-neutral and self-contained. An unmatched or unresolved tool call SHALL remain ineligible; a settled tool call and its output MAY be replayed together without losing either item.

#### Scenario: Quota rejection preserves complete tool history
- **GIVEN** a full input contains a tool call and its matching completed output
- **WHEN** the first account explicitly rejects before response creation
- **THEN** an eligible alternate account may receive the complete call and output exactly once

#### Scenario: Quota rejection cannot hand off an unsettled tool call
- **GIVEN** a full input contains a tool call without its matching output
- **WHEN** the first account explicitly rejects before response creation
- **THEN** no alternate account receives that incomplete history
