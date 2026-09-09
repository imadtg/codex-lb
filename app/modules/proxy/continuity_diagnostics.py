"""Bounded, content-free continuity decisions shared across proxy layers."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from hashlib import sha256
from typing import Protocol

from app.core.balancer import AccountState
from app.core.clock import REAL_CLOCK, Clock
from app.core.utils.request_id import get_request_id, get_request_scope_id
from app.db.models import Account

logger = logging.getLogger("app.modules.proxy.continuity")


def _emit(message: str, *args: str | int | float | bool | None, clock: Clock = REAL_CLOCK) -> None:
    """Attach wall and monotonic clocks so ordering survives wall-clock adjustments."""
    if logger.isEnabledFor(logging.INFO):
        logger.info(
            "observed_at_ns=%s monotonic_ns=%s process=%s " + message,
            int(clock.time() * 1_000_000_000),
            int(clock.monotonic() * 1_000_000_000),
            os.getpid(),
            *args,
        )


def correlation_hash(value: str | None) -> str | None:
    """Match existing continuity identifier hashing without logging raw tokens."""
    return f"sha256:{sha256(value.encode()).hexdigest()[:12]}" if value else None


def record_continuity_decision(
    *,
    stage: str,
    reason: str,
    input_count: int | None = None,
    stored_count: int | None = None,
    fingerprint_present: bool | None = None,
    manifest_present: bool | None = None,
) -> None:
    """Emit only implementation-defined reasons and scalar proof facts."""
    _emit(
        "continuity_decision version=1 request=%s scope=%s stage=%s reason=%s "
        "input_count=%s stored_count=%s fingerprint_present=%s manifest_present=%s",
        correlation_hash(get_request_id()),
        correlation_hash(get_request_scope_id()),
        stage,
        reason,
        input_count,
        stored_count,
        fingerprint_present,
        manifest_present,
    )


def record_selection_decision(
    *,
    selected_account_id: str | None,
    required_account_id: str | None,
    model: str | None,
    error_code: str | None,
    candidate_count: int,
    excluded_count: int,
    owner_restricted: bool,
) -> None:
    """Record the selector result; candidate count is not a quota-eligible count."""
    _emit(
        "continuity_selection version=1 request=%s scope=%s selected=%s required=%s "
        "model=%s outcome=%s error_code=%s candidates=%s excluded=%s owner_restricted=%s",
        correlation_hash(get_request_id()),
        correlation_hash(get_request_scope_id()),
        correlation_hash(selected_account_id),
        correlation_hash(required_account_id),
        correlation_hash(model),
        "selected" if selected_account_id else "unavailable",
        error_code
        if error_code
        in {
            "hard_affinity_owner_excluded",
            "hard_affinity_saturated",
            "continuity_owner_unavailable",
            "continuity_owner_policy_conflict",
            "usage_limit_reached",
            "conversation_owner_unavailable",
            "continuity_owner_conflict",
        }
        else correlation_hash(error_code),
        candidate_count,
        excluded_count,
        owner_restricted,
    )


def record_candidate_states(states: Sequence[AccountState]) -> None:
    """Record bounded selector inputs; statuses alone do not establish eligibility."""
    if not logger.isEnabledFor(logging.INFO):
        return
    request = correlation_hash(get_request_id())
    scope = correlation_hash(get_request_scope_id())
    for state in states[:64]:
        _emit(
            "continuity_candidate version=1 request=%s scope=%s account=%s status=%s "
            "primary_used=%s secondary_used=%s reset_at=%s cooldown_until=%s "
            "priority_used=%s priority_secondary_used=%s limit_scoped=%s "
            "health_tier=%s inflight_streams=%s ignore_standard_quota=%s",
            request,
            scope,
            correlation_hash(state.account_id),
            state.status.value,
            state.used_percent,
            state.secondary_used_percent,
            state.reset_at,
            state.cooldown_until,
            state.priority_used_percent,
            state.priority_secondary_used_percent,
            state.limit_scoped_usage,
            state.health_tier,
            state.inflight_streams,
            state.ignore_standard_quota,
        )
    _emit(
        "continuity_candidate_snapshot version=1 request=%s scope=%s total=%s omitted=%s",
        request,
        scope,
        len(states),
        max(0, len(states) - 64),
    )


def record_proof_mutation(
    *,
    action: str,
    session_id: str,
    owner_epoch: int,
    applied: bool,
    proof_preserved: bool,
) -> None:
    """Distinguish committed proof changes from fenced-out mutation attempts."""
    _emit(
        "continuity_proof_mutation version=1 request=%s scope=%s session=%s "
        "action=%s owner_epoch=%s applied=%s proof_preserved=%s",
        correlation_hash(get_request_id()),
        correlation_hash(get_request_scope_id()),
        correlation_hash(session_id),
        action,
        owner_epoch,
        applied,
        proof_preserved,
    )


def record_terminal_observation(
    *,
    request_id: str,
    archive_request_id: str | None,
    session_id: str | None,
    account_id: str,
    event_type: str | None,
    response_events: int,
    replay_count: int,
    downstream_visible: bool,
) -> None:
    """Observe an upstream terminal frame, not a promise of downstream delivery."""
    event = (
        event_type
        if event_type in {"response.completed", "response.failed", "response.incomplete", "error"}
        else "other"
    )
    _emit(
        "continuity_terminal version=1 request=%s archive_request=%s observer_request=%s "
        "session=%s account=%s event=%s "
        "response_events=%s replay_count=%s downstream_visible=%s",
        correlation_hash(request_id),
        correlation_hash(archive_request_id),
        correlation_hash(get_request_id()),
        correlation_hash(session_id),
        correlation_hash(account_id),
        event,
        response_events,
        replay_count,
        downstream_visible,
    )


class SelectionObservation(Protocol):
    @property
    def account(self) -> Account | None: ...
    @property
    def error_code(self) -> str | None: ...


def observe_selection_result[T: SelectionObservation](
    result: T,
    *,
    required_account_id: str | None,
    model: str | None,
    candidate_count: int,
    excluded_count: int,
    owner_restricted: bool,
) -> T:
    """Observe a result without changing its identity or reservation ownership."""
    record_selection_decision(
        selected_account_id=result.account.id if result.account else None,
        required_account_id=required_account_id,
        model=model,
        error_code=result.error_code,
        candidate_count=candidate_count,
        excluded_count=excluded_count,
        owner_restricted=owner_restricted,
    )
    return result


def record_retry_ownership(
    *,
    request_id: str,
    archive_request_id: str | None,
    account_id: str,
    hard_owner: bool,
    fresh_switch_allowed: bool,
    require_preferred: bool,
    account_bound_body: bool,
    operation_present: bool,
    hard_anchor: bool,
    owner_excluded: bool,
    response_events: int,
) -> None:
    """Expose the independent ownership gates immediately before retry reconnect."""
    _emit(
        "continuity_retry version=1 request=%s archive_request=%s account=%s "
        "hard_owner=%s fresh_switch_allowed=%s require_preferred=%s account_bound_body=%s "
        "operation_present=%s hard_anchor=%s owner_excluded=%s response_events=%s",
        correlation_hash(request_id),
        correlation_hash(archive_request_id),
        correlation_hash(account_id),
        hard_owner,
        fresh_switch_allowed,
        require_preferred,
        account_bound_body,
        operation_present,
        hard_anchor,
        owner_excluded,
        response_events,
    )
