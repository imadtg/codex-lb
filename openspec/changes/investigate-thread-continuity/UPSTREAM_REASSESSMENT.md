# Upstream reassessment — September 9, 2026

## Decision

The candidate contains useful fixes to actual recovery predicates and proof retention, but it is not yet a decisive fix for the whole dead-owner class. New INFO diagnostics exposed live-owner quota-rejection paths that still need a third client request: direct HTTP rejects response-owned input IDs; WebSocket retry retains an excluded hard/operation owner after accepting the projected history. Do not submit the combined checkout as closing #1707. Submit narrow reproduced fixes with attribution; keep the quota-on-live-socket reproducer as an explicit blocker to the comprehensive claim.

The approach is not novel in principle. Both projects distinguish portable full history from a continuation tied to a credential. Our contributions primarily repair inconsistencies in that existing contract and make the decisions observable. We cannot know why an unreported specific defect was not noticed; the public record supports missing coverage and integration gaps, not an assertion that maintainers ignored the idea.

## Current main snapshots

- codex-lb: [`2a093177a46e7abf9beb0998c4e302fd3efae242`](https://github.com/Soju06/codex-lb/commit/2a093177a46e7abf9beb0998c4e302fd3efae242), 11 commits beyond our `d3f63331` base. The candidate has **not** been rebased to this new head. The compare and current replay/repository source were inspected.
- CLIProxyAPI: [`7fac6b15bcfe5ea55c18c9eaec8e5b7e6457d974`](https://github.com/router-for-me/CLIProxyAPI/commit/7fac6b15bcfe5ea55c18c9eaec8e5b7e6457d974). Inspected the native Responses WebSocket handler, credential selector, executor stream paths and quota helper from that exact SHA, alongside PRs and issues.

Public API snapshots and source files are retained under `audit-artifacts/continuity-observability/upstream/` in the parent workspace. Status is a dated observation, not a prediction of merge readiness.

Current codex-lb main adds subscription-overflow/model-source groundwork and malformed-JSON membership guards. Its new `PortabilityVerdict` reports decline reasons for **cross-provider model sources**; the established account-neutral replay predicate still returns a boolean. Our account-continuity diagnostics fit that direction, but a rebase should align naming rather than invent a competing portability policy. A Lite tool bundle may be portable between Codex accounts but unsupported by a generic provider: these classifiers must not be equated. [Current replay-safety source](https://github.com/Soju06/codex-lb/blob/2a093177a46e7abf9beb0998c4e302fd3efae242/app/modules/proxy/replay_safety.py)

## codex-lb: what has already been tried

| Work | Current observation | Relationship to our candidate |
|---|---|---|
| [#2078](https://github.com/Soju06/codex-lb/pull/2078) exhausted-account reactivation | Merged; already in our base | Upstream's quota-state fix, not our invention |
| [#2121](https://github.com/Soju06/codex-lb/pull/2121) complete tool batch plus new user input | Open; API reports conflicts. Maintainer reproduced failure on main and success with patch; September 8 review requests spec-union rebase and contributor attribution | Integrated with attribution. Strong precedent for our proof-preserving approach |
| [#2069](https://github.com/Soju06/codex-lb/pull/2069) unanchored quota replay | Open. Latest comments report a genuine CI failure from over-strict host-heartbeat matching, fixed at `085640b2` | Integrated earlier; exact current-head differences still need reconciliation before submission |
| [#2111](https://github.com/Soju06/codex-lb/pull/2111) publish response owners before delivery | Open; API reports conflicts; maintainer independently verified the race fix and described union-resolvable conflicts | Integrated with attribution; not evidence of upstream rejecting the solution |
| [#2086](https://github.com/Soju06/codex-lb/pull/2086) prefix-settled outputs | Open. Maintainer reproduced a Lite-prefix raw-ID bypass, questioned the real-client reachability of the proposed state, and requested a corrected spec delta | Deliberately not imported. More permissive proof is not automatically a correct fix |
| [#1900](https://github.com/Soju06/codex-lb/pull/1900) persist complete bridge transcripts | Open; proposes durable complete replay snapshots and recovery for otherwise incomplete continuations | Broader reconstruction direction; not interchangeable with retaining our existing count/fingerprint/manifest proof |
| [#2207](https://github.com/Soju06/codex-lb/pull/2207) automatic quota failover | Open; author requests review. Proposal allows bounded pre-visible quota retries while preserving hard ownership | Helpful for movable requests, but explicitly not a solution to hard-continuation migration |
| [#2001](https://github.com/Soju06/codex-lb/pull/2001) release payload-derived owner after early 429 | Open; distinguishes early explicit quota rejection from ambiguous provider acceptance | Adjacent to the newly reproduced live quota path; warrants focused integration evaluation |
| [#2075](https://github.com/Soju06/codex-lb/pull/2075), [#2081](https://github.com/Soju06/codex-lb/issues/2081) frame-less disconnects | Open; transport-health attribution and lost owner evidence | Prevent a healthy owner becoming falsely unavailable; do not themselves migrate a genuinely exhausted owner |

The maintainer's [September 8 tracker update](https://github.com/Soju06/codex-lb/issues/1707#issuecomment-5586440512) explicitly separates shipped poison/affinity fixes from remaining tool-manifest, quota, transport and excluded-owner problems. This is already an upstream family of issues. The additional value here is a real Codex process witness plus the previously untested schema, fingerprint and proof-retirement interactions.

## CLIProxyAPI: same boundary, different recovery machinery

[#4522](https://github.com/router-for-me/CLIProxyAPI/pull/4522) is merged. Current main retains its important design: an incremental native-WebSocket continuation stays on its transport/credential; a selected credential failure can be suppressed and translated into a 1012 close requesting a full replay on a new connection. Canonical fallback transcript state is separate, and tool-cache updates commit after successful forwarding. This is a precedent for requesting supported reconstruction, not for blindly removing an anchor from a delta. [Pinned current handler](https://github.com/router-for-me/CLIProxyAPI/blob/7fac6b15bcfe5ea55c18c9eaec8e5b7e6457d974/sdk/api/handlers/openai/openai_responses_websocket.go)

The current selector still enforces a future credential-wide quota deadline before per-model availability. That substantiates the stale-cooldown mechanism; issue descriptions about actual deployments remain user reports rather than our own live reproductions. [Pinned selector](https://github.com/router-for-me/CLIProxyAPI/blob/7fac6b15bcfe5ea55c18c9eaec8e5b7e6457d974/sdk/cliproxy/auth/selector.go)

- [#5619](https://github.com/router-for-me/CLIProxyAPI/issues/5619) reports one Codex model bucket cooling the whole credential; [#5620](https://github.com/router-for-me/CLIProxyAPI/pull/5620) proposes optional model-scoped handling. This resembles the user's reserve-model concern, but does not prove that concern caused the original codex-lb incident.
- [#5639](https://github.com/router-for-me/CLIProxyAPI/issues/5639) and [#5404](https://github.com/router-for-me/CLIProxyAPI/issues/5404) report stale cooldowns despite restored quota. [#5609](https://github.com/router-for-me/CLIProxyAPI/pull/5609), still open, proposes a bounded cooldown ceiling. Its tradeoff is periodic inference retries on accounts that may remain exhausted; it is not a drop-in replacement for codex-lb's usage refresh logic.
- [#4248](https://github.com/router-for-me/CLIProxyAPI/pull/4248) proposed a paid-plan retry-hint ceiling and is **closed unmerged**. No explanatory issue comments were returned in this inspection; closure alone does not establish rejection on technical grounds or supersession.
- [#5420](https://github.com/router-for-me/CLIProxyAPI/pull/5420) and [#5566](https://github.com/router-for-me/CLIProxyAPI/pull/5566) remain open around tools during transcript replacement and prewarm context during compact replay. They reinforce the need to test reconstruction fidelity.
- [#5115](https://github.com/router-for-me/CLIProxyAPI/pull/5115) merged optional stream-bootstrap buffering and overload failover. That addresses the pre-visible retry window; it does not make account-owned state universally portable.

Moving to CLIProxyAPI is therefore not an evidence-backed guarantee of eliminating the symptom. Port back focused protocol ideas and tests, not its scheduler or its cooldown ceilings wholesale.

## What is ours, and the right PR boundaries

1. **Codex compatibility:** reasoning context/correlation controls, local namespaces and their parameter schemas, web-search booleans. Demonstrate a normal client shape rejected before the patch and accepted after; retain malformed and account-owned negatives.
2. **Fingerprint consistency:** match the established namespace-stripped sent representation while retaining exact equality for actual content and call identity.
3. **Proof lifetime:** retiring a response anchor must not erase the completed transcript evidence. Same-owner poison retention remains fenced; actual account rebind still clears old proof. Include stale-epoch and concurrent-new-anchor negative cases.
4. **Selector termination:** an explicitly excluded hard owner is not transient saturation. Keep this separate from migration policy.
5. **Observability:** stable decision reasons, request correlation, bounded state snapshots and a redacted exporter, independently reviewable without claiming broader recovery.
6. **Live quota recovery:** currently a blocker, not ready for a solved claim. Preserve the validated replay body, then implement a dedicated durable-operation-fenced handoff that retires the old attempt, settles its reservation, establishes replacement ownership and cannot double-dispatch accepted work. Do not simply clear `operation_id` or the client's turn-state token.

Our imported PRs should be dependencies or author-attributed cherry-picks, not republished as original work. Rebase onto the inspected latest main, resolve the newly overlapping `replay_safety.py` changes, run the relevant SQLite/PostgreSQL and transport CI, and split the integration checkout into atomic concerns before calling it PR-ready. No commits, PRs, comments, deployment or live mutations were made in this reassessment.
