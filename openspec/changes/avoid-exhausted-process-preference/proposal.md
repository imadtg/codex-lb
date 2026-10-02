# Change: avoid-exhausted-process-preference

## Why

On 2026-10-02, a new HTTP-bridge thread inherited a process-level account
preference just after that account was manually reactivated. Its fresh weekly
usage row was 100% with no credits, while another eligible Plus account had
remaining usage. Selection admitted the new thread on the exhausted account,
which rejected it. That first admission created account-specific bridge
continuity, so subsequent retries could not simply move to the available
account.

The process preference is only a default for new threads. It is not an owner
of a response, file, tool result, or established thread.

## What Changes

Before honoring a process preference for a new soft prompt-cache thread,
selection checks whether the preferred account has no observed remaining
usage and whether a scoped, selectable sibling has observed remaining usage.
In that case the new thread starts on the sibling. The process preference
itself is left intact; a hard continuation owner is untouched. If no sibling
can serve, the preferred account remains eligible for an upstream attempt.

## Evidence

The integration regression uses real account/usage/sticky repositories and
the dashboard reactivation route. It fails on deployed commit 5e456ce3 by
selecting the exhausted preferred account; with this change it selects the
available account, records the new thread mapping, retains the process
preference, and still admits the preferred account when no sibling exists.
