"""Bounded, account-correlatable evidence for failed routing decisions."""

from __future__ import annotations

import hashlib

from app.core.balancer import AccountState
from app.db.models import Account


def account_label(account_id: str | None) -> str | None:
    if account_id is None:
        return None
    return hashlib.sha256(account_id.encode()).hexdigest()[:12]


def account_snapshots(accounts: list[Account], candidate_ids: set[str]) -> list[dict[str, object]]:
    return [
        {
            "account": account_label(account.id),
            "candidate": account.id in candidate_ids,
            "plan": account.plan_type,
            "persisted_status": account.status.value,
            "persisted_reset_at": account.reset_at,
            "persisted_blocked_at": account.blocked_at,
            "routing_policy": account.routing_policy,
        }
        for account in accounts[:16]
    ]


def state_snapshots(states: list[AccountState]) -> list[dict[str, object]]:
    return [
        {
            "account": account_label(state.account_id),
            "status": state.status.value,
            "primary_used": state.used_percent,
            "secondary_used": state.secondary_used_percent,
            "quota_evidence_primary": state.priority_used_percent,
            "quota_evidence_secondary": state.priority_secondary_used_percent,
            "reset_at": state.reset_at,
            "primary_reset_at": state.primary_reset_at,
            "secondary_reset_at": state.secondary_reset_at,
            "blocked_at": state.blocked_at,
            "cooldown_until": state.cooldown_until,
            "error_count": state.error_count,
            "last_error_at": state.last_error_at,
            "health_tier": state.health_tier,
            "routing_policy": state.routing_policy,
            "inflight_creates": state.inflight_response_creates,
            "inflight_streams": state.inflight_streams,
        }
        for state in states[:16]
    ]
