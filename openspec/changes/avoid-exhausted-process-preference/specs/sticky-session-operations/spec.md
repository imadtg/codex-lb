## MODIFIED Requirements

### Requirement: New threads treat process account seeds as preferences

A process-level account seed MUST remain a preference for a thread that has no
thread owner. When the seed account has no observed remaining applicable usage
and another scoped, selectable account has observed remaining applicable usage,
selection MUST admit the new thread on the available account and persist its
soft mapping without rewriting the process seed. If no alternative can serve,
local usage alone MUST NOT prevent an upstream attempt on the seed account.
Existing hard continuation ownership MUST remain unchanged.

#### Scenario: A new thread bypasses an exhausted process preference
- **GIVEN** a process preference points to account A, but the new thread has no thread owner
- **AND** account A is active after manual reactivation but its applicable usage is at 100 percent
- **AND** another account has remaining applicable usage and is eligible for the requested model
- **WHEN** the new thread selects an account for its first upstream response
- **THEN** selection uses the available account and persists that account as the new thread's soft owner
- **AND** the process preference remains unchanged for independent future threads
- **AND** an already established hard continuation owner is not changed by this rule
- **AND** if no alternative can serve, the process preference remains eligible for an upstream attempt
