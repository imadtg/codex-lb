from __future__ import annotations

import asyncio
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.scheduling import leader_election as leader
from app.db import session as db

pytestmark = pytest.mark.integration


@asynccontextmanager
async def stalled_store(tmp_path: Path):
    path = tmp_path / "owned.db"
    setup = sqlite3.connect(path)
    setup.execute("PRAGMA journal_mode=WAL")
    setup.execute("CREATE TABLE pressure (value INTEGER)")
    setup.execute(
        "CREATE TABLE scheduler_leader (id INTEGER PRIMARY KEY, leader_id TEXT NOT NULL, "
        "acquired_at DATETIME NOT NULL, expires_at DATETIME NOT NULL)"
    )
    setup.commit()
    setup.close()
    entered, release = threading.Event(), threading.Event()

    def pause_writer():
        entered.set()
        assert release.wait(10)
        return 0

    engine = db._create_main_engine(f"sqlite+aiosqlite:///{path}")

    @event.listens_for(engine.sync_engine, "connect")
    def install(connection, record):
        connection.create_function("pause_writer", 0, pause_writer)

    factory = async_sessionmaker(engine, class_=db.SessionLocal.class_, expire_on_commit=False)
    try:
        yield path, engine, factory, entered, release
    finally:
        release.set()
        await engine.dispose()


@pytest.mark.asyncio
async def test_cancelled_returning_writer_recovers_without_gc(tmp_path):
    async with stalled_store(tmp_path) as (path, engine, factory, entered, release):
        async with factory() as session:
            await session.execute(
                text("CREATE TRIGGER pause_insert BEFORE INSERT ON pressure BEGIN SELECT pause_writer(); END")
            )
            await session.commit()

        async def write():
            async with factory() as session:
                await session.execute(text("INSERT INTO pressure VALUES (1) RETURNING value"))
                await session.commit()

        task = asyncio.create_task(write())
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            await asyncio.sleep(2.4)
            assert not task.done(), "caller cancellation abandoned native SQLite execution"
            task.cancel()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            probe = sqlite3.connect(path, timeout=0.1)
            try:
                probe.execute("BEGIN IMMEDIATE")
                probe.rollback()
                assert probe.execute("SELECT COUNT(*) FROM pressure").fetchone()[0] == 0
            finally:
                probe.close()
            async with factory() as session:
                await session.execute(text("INSERT INTO pressure VALUES (2)"))
                await session.commit()
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelled_renewal_observer_is_singleflight_and_late_result_is_fenced(tmp_path, monkeypatch):
    async with stalled_store(tmp_path) as (path, engine, factory, entered, release):
        monkeypatch.setattr(db, "_background_session_factory", factory)
        monkeypatch.setattr(
            leader,
            "get_settings",
            lambda: SimpleNamespace(leader_election_enabled=True, leader_election_ttl_seconds=60),
        )
        election = leader.LeaderElection("test-owner")
        assert await election.try_acquire()
        async with factory() as session:
            await session.execute(
                text("CREATE TRIGGER pause_renew BEFORE UPDATE ON scheduler_leader BEGIN SELECT pause_writer(); END")
            )
            await session.commit()
        first = asyncio.create_task(election.renew())
        second = None
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            second = asyncio.create_task(election.renew())
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            election._demote()
            release.set()
            assert not await second
            assert not election.is_leader
            assert election._lease_deadline is None
            async with factory() as session:
                await session.execute(text("INSERT INTO pressure VALUES (3)"))
                await session.commit()
        finally:
            release.set()
            await asyncio.gather(first, *([second] if second else []), return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase, expected_rows", [("commit", 1), ("rollback", 0)])
async def test_cancellation_during_transaction_end_retains_cleanup(tmp_path, phase, expected_rows):
    async with stalled_store(tmp_path) as (path, engine, factory, entered, release):
        session = factory()
        await session.execute(text("INSERT INTO pressure VALUES (4)"))

        def pause_end(connection):
            connection.exec_driver_sql("SELECT pause_writer()")

        event.listen(engine.sync_engine, phase, pause_end)
        operation = asyncio.create_task(getattr(session, phase)())
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            operation.cancel()
            await asyncio.sleep(0.05)
            assert not operation.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await operation
            probe = sqlite3.connect(path, timeout=0.1)
            try:
                probe.execute("BEGIN IMMEDIATE")
                probe.rollback()
                assert probe.execute("SELECT COUNT(*) FROM pressure").fetchone()[0] == expected_rows
            finally:
                probe.close()
        finally:
            release.set()
            await asyncio.gather(operation, return_exceptions=True)
            event.remove(engine.sync_engine, phase, pause_end)
            await session.close()


@pytest.mark.asyncio
async def test_admission_across_engines_is_bounded_and_readers_remain_concurrent(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_SQLITE_BUSY_TIMEOUT_SECONDS", 0.1)
    async with stalled_store(tmp_path) as (path, engine, factory, entered, release):
        second_engine = db._create_main_engine(f"sqlite+aiosqlite:///{path}")
        second_factory = async_sessionmaker(second_engine, class_=db.SessionLocal.class_)
        try:
            async with factory() as first:
                await first.execute(text("INSERT INTO pressure VALUES (5)"))
                async with second_factory() as second:
                    assert (await second.execute(text("SELECT COUNT(*) FROM pressure"))).scalar_one() == 0
                    with pytest.raises(
                        (sqlite3.OperationalError, OperationalError), match="local writer admission timeout"
                    ):
                        await second.execute(text("INSERT INTO pressure VALUES (6)"))
                    await second.rollback()
                await first.commit()
            async with second_factory() as second:
                async with second.begin():
                    await second.execute(text("INSERT INTO pressure VALUES (7)"))
                    async with second.begin_nested():
                        await second.execute(text("INSERT INTO pressure VALUES (8)"))
            async with factory() as first:
                assert (await first.execute(text("SELECT COUNT(*) FROM pressure"))).scalar_one() == 3
        finally:
            await second_engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_session_use_is_rejected_before_driver_dispatch(tmp_path):
    from sqlalchemy.exc import InvalidRequestError

    async with stalled_store(tmp_path) as (path, engine, factory, entered, release):
        async with factory() as session:
            first = asyncio.create_task(session.execute(text("SELECT pause_writer()")))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                with pytest.raises(InvalidRequestError, match="Concurrent use"):
                    await session.execute(text("SELECT 1"))
                release.set()
                assert (await first).scalar_one() == 0
            finally:
                release.set()
                await asyncio.gather(first, return_exceptions=True)


@pytest.mark.asyncio
async def test_shutdown_reports_unclean_without_reclaiming_running_driver(tmp_path, monkeypatch):
    async with stalled_store(tmp_path) as (path, engine, factory, entered, release):
        monkeypatch.setattr(db, "_SQLITE_TEARDOWN_TIMEOUT_SECONDS", 0.02)
        async with factory() as session:
            operation = asyncio.create_task(session.execute(text("SELECT pause_writer()")))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                operation.cancel()
                assert not await db.close_db()
                assert not operation.done()
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await operation
                async with factory() as recovered:
                    await recovered.execute(text("INSERT INTO pressure VALUES (9)"))
                    await recovered.commit()
            finally:
                release.set()
                await asyncio.gather(operation, return_exceptions=True)


@pytest.mark.asyncio
async def test_writer_scope_serializes_predicates_and_does_not_grant_child_reentrancy(tmp_path):
    async with stalled_store(tmp_path) as (path, engine, factory, entered, release):
        predicate_read = asyncio.Event()
        finish_first = asyncio.Event()
        child_started = asyncio.Event()
        child = None

        async def insert_once():
            async with factory() as session:
                async with db.sqlite_writer_section():
                    child_started.set()
                    count = (await session.execute(text("SELECT COUNT(*) FROM pressure"))).scalar_one()
                    if not count:
                        await session.execute(text("INSERT INTO pressure VALUES (10)"))
                    await session.commit()

        async def first_writer():
            nonlocal child
            async with factory() as session:
                async with db.sqlite_writer_section():
                    assert (await session.execute(text("SELECT COUNT(*) FROM pressure"))).scalar_one() == 0
                    predicate_read.set()
                    # Child inherits the scope flag, but owns a different session.
                    child = asyncio.create_task(insert_once())
                    await finish_first.wait()
                    await session.execute(text("INSERT INTO pressure VALUES (10)"))
                    await session.commit()

        first = asyncio.create_task(first_writer())
        try:
            await predicate_read.wait()
            await child_started.wait()
            await asyncio.sleep(0.05)
            assert child is not None and not child.done()
            async with factory() as reader:
                assert (await reader.execute(text("SELECT COUNT(*) FROM pressure"))).scalar_one() == 0
            finish_first.set()
            await first
            await child
            async with factory() as reader:
                assert (await reader.execute(text("SELECT COUNT(*) FROM pressure"))).scalar_one() == 1
        finally:
            finish_first.set()
            await asyncio.gather(first, *([child] if child else []), return_exceptions=True)
