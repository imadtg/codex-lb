# Beta.8 integration evidence

Base: published v1.25.0-beta.8 (`bb4db9d0`). Source of local behavior: `a23315e1`, based on beta.7. Live deployment is left unchanged while validating.

## Implementation decisions

- Keep upstream #2390/#2397 durable owner retirement, including its explicit client-anchor and file-owner restrictions.
- Replace local excluded-owner selector branch and result-type relocation with upstream #2381. Upstream carries a boolean reason through selection, avoiding our alternate error envelope.
- Keep upstream #2384 rejection classifier and request logging. Attach local bounded request-stage evidence without replacing the upstream rejection contract.
- Drop the local missing-proof fallback from `durable_full_resend_allows_account_neutral_replay`; upstream deliberate owner retirement now owns that decision. This does not assert all loss-of-proof incidents are solved.
- Retain fenced explicit quota handoff: unmodified beta.8 fails the public `quota_bridge` scenario; candidate passes, including a follow-up. More variants are pending.
- Retain plaintext host input validation and client fingerprint preservation provisionally, pending matrix results.
- Retain sequenced prewarm/capacity recovery provisionally; upstream still deliberately refuses sequenced accepted capacity failures.

## Test method

The same probe script launches each checkout as a separate process with disposable HOME/data/database and synthetic accounts imported through the dashboard API. Requests and quota failures are delivered over public HTTP/WebSocket interfaces. No live data is copied or modified and no SQL writes manufacture replay proof. Provider mocks record dispatched accounts, body, anchor and turn-state presence; positive and negative controls check these wire results.

The old optional real-Codex integration test is retained as historical coverage but uses in-process application fixtures; it is not described as a public-process test. The metadata refresh background task can fetch public pricing metadata; synthetic inference traffic targets loopback only.

Evidence logs are under `/tmp/lb-beta8-*`; final counts and portable report summaries will be recorded after completion.
