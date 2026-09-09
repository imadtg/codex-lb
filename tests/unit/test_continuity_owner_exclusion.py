"""Upstream #2163: distinguish impossible selection from recoverable saturation."""

import pytest

from app.db.models import StickySessionKind
from app.modules.proxy._service.support import _account_selection_recovery_sleep_seconds
from app.modules.proxy.affinity import _codex_session_selection_key
from tests.unit.test_load_balancer_concurrency import _make_cap_spillover_balancer

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("legacy", [True, False])
async def test_excluded_hard_owner_is_not_a_recovery_wait(legacy):
    balancer, owner, alternate, repo = _make_cap_spillover_balancer("excluded-owner")
    raw = "synthetic-session"
    key = _codex_session_selection_key(raw) if legacy else "synthetic-thread"
    repo.account_ids_by_key = {raw if legacy else key: owner.id}
    result = await balancer.select_account(
        sticky_key=key,
        sticky_kind=StickySessionKind.CODEX_SESSION,
        sticky_source="session_header" if legacy else "thread_header",
        legacy_sticky_key=raw if legacy else None,
        exclude_account_ids={owner.id},
    )
    assert result.account is None
    assert result.error_code == "hard_affinity_owner_excluded"
    assert _account_selection_recovery_sleep_seconds(result) is None
    assert repo.deleted == []
    assert repo.upserts == []


async def test_unexcluded_temporarily_unavailable_owner_keeps_recovery_wait():
    import time

    from app.db.models import AccountStatus

    balancer, owner, _, repo = _make_cap_spillover_balancer("unavailable-owner")
    owner.status = AccountStatus.RATE_LIMITED
    owner.reset_at = int(time.time()) + 1800
    owner.blocked_at = int(time.time())
    repo.account_ids_by_key = {"synthetic-thread": owner.id}
    result = await balancer.select_account(
        sticky_key="synthetic-thread", sticky_kind=StickySessionKind.CODEX_SESSION, sticky_source="thread_header"
    )
    assert result.account is None
    assert result.error_code == "hard_affinity_saturated"
    assert _account_selection_recovery_sleep_seconds(result) == 2.0
