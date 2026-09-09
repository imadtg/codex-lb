"""Offline beta/main comparison using synthetic in-memory quota state; no DB or network.

Run with the target environment interpreter and that version on PYTHONPATH.
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from app.db.models import Account, AccountStatus, UsageHistory
from app.modules.proxy.load_balancer import RuntimeState, _state_from_account

now = 1700000000.0


def date(t):
    return datetime.fromtimestamp(t, timezone.utc).replace(tzinfo=None)


a = Account(
    id="synthetic",
    email="a@example.invalid",
    plan_type="plus",
    status=AccountStatus.RATE_LIMITED,
    reset_at=int(now + 1800),
    blocked_at=int(now - 130),
    access_token_encrypted=b"a",
    refresh_token_encrypted=b"r",
    id_token_encrypted=b"i",
    last_refresh=date(now),
)


def usage(window, used):
    return UsageHistory(
        account_id=a.id,
        window=window,
        used_percent=used,
        reset_at=int(now + 1800),
        recorded_at=date(now - 1),
        window_minutes=300 if window == "primary" else 10080,
    )


with patch("time.time", return_value=now), patch("app.modules.proxy.load_balancer.utcnow", return_value=date(now)):
    s = _state_from_account(
        account=a,
        primary_entry=usage("primary", 100),
        secondary_entry=usage("secondary", 16),
        runtime=RuntimeState(cooldown_until=now - 1, blocked_at=now - 130),
    )
    print(json.dumps({"status": s.status.value, "reset_at": s.reset_at, "used_percent": s.used_percent}))
