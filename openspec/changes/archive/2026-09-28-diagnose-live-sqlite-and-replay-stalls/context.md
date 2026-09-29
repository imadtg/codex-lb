# Redarchy incident investigation, 2026-09-28

## Runtime and scope
Live authority is Redarchy `dev.mise.codex-lb.service` and `~/.codex-lb/`. The installed uv package direct_url.json identifies e5367c15e269aded810c24fad102660223157f19, a direct child of 581de1ce; replay_safety.py and streaming/retry.py exactly match the prior fix. The service now resolves fork downstream through isolated uvx. This investigation neither restarted it nor edited its database.

## SQLite contention
Journal evidence shows unrelated writers (scheduler, ring heartbeat, key last-used, sticky mappings and durable bridge) failing, with first user-facing 500 at 15:26:32 UTC and broad failures through 21:07 UTC. Disk had hundreds of GB free and only the proxy process held database file descriptors. The existing post-transaction watchdog emitted no sqlite_long_write_transaction attribution. A wedged rollback at 18:51:06 UTC reported unknown write age; the retention pass at 15:25:28 took 40.7 seconds. Neither is proof of the original holder.

The new SQLITE_BUSY/LOCKED hook reports up to four observed same-process writer candidates, at most once per engine per 30 seconds. It includes age, lifecycle phase, task and app stack locations, and only fixed SQL operation labels. It excludes SQL literals and parameters. Candidate writers are not proven kernel lock owners; absent candidates can mean an untracked driver operation, another process or an unobserved acquisition. The isolated SQLite regression holds a real transaction open, forces a competing engine to encounter lock failure, checks immediate attribution and rate limiting, then checks that a released transaction is absent under an untracked holder.

## Transport
Parallel journal inspection found 20 upstream reader failures that day: 19 had no pending operation and zero response events, one at 15:28:59 UTC interrupted an active response after 18 events. Recovery encountered previous_response_not_found at 15:29:04, then fresh-resend continuations completed at 15:29:21 and 15:29:35. Connection observer hashes can persist across operations, so they alone cannot prove which logical attempt delivered which completion.

A separate host network outage around 21:39–21:43 UTC caused concurrent Network is unreachable errors. Four streams logged retry progress and recovered at 21:43:01–21:43:07. This already has useful network retry instrumentation. Idle reader warnings are noisy, not proof that an active response was lost.

## Prefix mismatch
Six refusals at 19:16 UTC map to T3 thread 308abf5d-877f-4287-98c9-8aff67316e99, Codex thread 01a0c488-a16c-7402-aebd-938a7899d6a0. Logs show 269 incoming items against a stored count of 265. No compaction occurred that day. Earlier stored upstream deltas match portions of later full history, but those deltas do not reconstruct the rejected body or historical anchor hash. Network-unreachable failures overlapped 19:15–19:16, and the same owner became available at 19:16:38 and completed the continuation by 19:19. Quota depletion and substantive context loss are not established.

The prefix diagnostic logs stored/raw/forwarding-normalized prefix hashes (12 hex chars), counts, and boolean anchor/manifest markers, tied to hashed request/scope identifiers. It does not store rejected bodies or relax the proof. Hash equality enables correlation; a hash is not anonymization for low-entropy guessed content. Next recurrence: correlate http_bridge_prefix_proof_mismatch with continuity_decision, selection outcomes and network recovery; compare counts and normalized hashes before proposing any eligibility relaxation.

## Next recurrence
Start with the current journal and exact installed source revision. For SQLite look for sqlite_busy_live_writers and correlate candidate task app-stack locations with retention, request and teardown lifecycle logs. Reproduce the identified holder path in an isolated file-backed database before changing transactions. For transport distinguish pending operations, output already delivered, downstream terminal outcome and network-recovery completion. For replay retain the strict full-context proof until concrete rejected-prefix evidence supports a narrower rule change.
