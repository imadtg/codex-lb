# Thread continuity failure investigation

## Why
An existing T3/Codex thread remained bound to an exhausted account after beta.4 poisoned-anchor abandonment while alternatives had quota. Earlier recovery required account pause and a new provider session. We need executable evidence rather than another speculative configuration change.

## Scope
Add offline, content-redacting instrumentation over the real replay classifier; synthetic tests for payload and ownership boundaries; route-level fault injection using the real selector and database; an evidence-backed failure map and staged upstream fix plan. Implement scoped fixes for Codex 0.152 reasoning/correlation controls, namespace declarations and calls, forwarding-normalized prefix comparison, and explicitly excluded hard-owner selection. Preserve account-owned-state checks and all transport ownership rules.

## Acceptance
Reproduce a stranded continuation with a bounded test, demonstrate a working account switch as a control, explain exact classifier rejection branches without logging conversation content, identify existing tests and missing scenarios, and separate proven local behavior from upstream protocol assumptions. No finite suite establishes absence of all future provider failures; each proposed guarantee must name its boundary and corresponding regression.
