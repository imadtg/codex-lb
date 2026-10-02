# Change: settle-force-probe-from-snapshot

## Why

On 2026-10-02 Redarchy received HTTP 200 for an operator Force Probe, but
advisory settlement raised SQLAlchemy DetachedInstanceError after the
repository context closed. The route still returned 200, while the local
probe-health observation was lost.

## What Changes

Keep a detached, complete snapshot of account and usage rows loaded inside
the repository context. The existing health-version check and eligibility
rules still decide whether that observation may settle.

## Evidence

A dashboard route regression using the real load balancer reproduces the
journal traceback on deployed commit 5e456ce3 and passes with row snapshots.
