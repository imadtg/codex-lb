from __future__ import annotations

import asyncio
import sqlite3
import threading
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import sqlite_writer_health as writer_health
from app.db.session import _configure_sqlite_engine

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_real_busy_hook_readiness_and_recovery(async_client, monkeypatch, tmp_path: Path):
    path = tmp_path / "writer.db"
    url = f"sqlite+aiosqlite:///{path}"
    setup = sqlite3.connect(path)
    setup.execute("PRAGMA journal_mode=WAL")
    setup.execute("CREATE TABLE pressure (value INTEGER)")
    setup.commit()
    setup.execute("BEGIN IMMEDIATE")
    setup.execute("INSERT INTO pressure VALUES (1)")
    engine = create_async_engine(url)
    _configure_sqlite_engine(engine.sync_engine, enable_wal=True)
    monkeypatch.setattr(writer_health, "_FAILURE_WINDOW_SECONDS", 0.05)
    monkeypatch.setattr(writer_health, "_PROBE_INTERVAL_SECONDS", 0)
    from app.modules.health import api as health_api

    monkeypatch.setattr(health_api, "engine", engine)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("PRAGMA busy_timeout=10"))
            assert (await connection.execute(text("SELECT 1"))).scalar_one() == 1
            for _ in range(2):
                with pytest.raises(Exception, match="database is locked"):
                    await connection.execute(text("INSERT INTO pressure VALUES (2)"))
        await asyncio.sleep(0.06)
        response = await async_client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["detail"] == "Service SQLite writer slot is unavailable"
        assert (await async_client.get("/health/live")).status_code == 200
        setup.rollback()
        assert (await async_client.get("/health/ready")).status_code == 200
        async with engine.begin() as connection:
            await connection.execute(text("INSERT INTO pressure VALUES (3)"))
    finally:
        setup.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_brief_contention_does_not_probe_or_fail_readiness(monkeypatch, tmp_path: Path):
    path = tmp_path / "brief.db"
    writer_health.record_sqlite_busy(path)
    monkeypatch.setattr(writer_health, "_probe_writer_slot", lambda _: pytest.fail("unexpected probe"))
    assert await writer_health.sqlite_writer_is_ready(f"sqlite+aiosqlite:///{path}")
    assert await writer_health.sqlite_writer_is_ready("sqlite+aiosqlite:///:memory:")
    assert await writer_health.sqlite_writer_is_ready("postgresql+asyncpg://localhost/example")


@pytest.mark.asyncio
async def test_probe_has_one_owner_and_caller_cancellation_does_not_cancel_worker(monkeypatch, tmp_path: Path):
    path = tmp_path / "owned.db"
    url = f"sqlite+aiosqlite:///{path}"
    monkeypatch.setattr(writer_health, "_FAILURE_WINDOW_SECONDS", 0.05)
    writer_health.record_sqlite_busy(path)
    writer_health.record_sqlite_busy(path)
    entered = threading.Event()
    release = threading.Event()
    probe_count = 0

    def owned_probe(path):
        nonlocal probe_count
        probe_count += 1
        entered.set()
        assert release.wait(timeout=5)
        return True

    monkeypatch.setattr(writer_health, "_probe_writer_slot", owned_probe)
    await asyncio.sleep(0.06)
    first = asyncio.create_task(writer_health.sqlite_writer_is_ready(url))
    assert await asyncio.to_thread(entered.wait, 2)
    second = asyncio.create_task(writer_health.sqlite_writer_is_ready(url))
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    release.set()
    assert await second
    assert probe_count == 1
    assert await writer_health.sqlite_writer_is_ready(url)


@pytest.mark.asyncio
async def test_non_lock_probe_failure_does_not_create_database(monkeypatch, tmp_path: Path, caplog):
    path = tmp_path / "missing.db"
    monkeypatch.setattr(writer_health, "_FAILURE_WINDOW_SECONDS", 0.05)
    writer_health.record_sqlite_busy(path)
    writer_health.record_sqlite_busy(path)
    await asyncio.sleep(0.06)
    assert not await writer_health.sqlite_writer_is_ready(f"sqlite+aiosqlite:///{path}")
    assert not path.exists()
    assert "sqlite_writer_probe_failed" in caplog.text
    assert "sqlite_writer_slot_held" not in caplog.text
