"""Disposable subprocess fault control. Imported only by the test harness."""

import asyncio
import sqlite3
import threading

from sqlalchemy import event, text

from app.db import session as db
from app.db.sqlite_utils import sqlite_db_path_from_url
from app.main import app

entered = threading.Event()
release = threading.Event()
owner = None
cancel_observed = False


def pause_writer():
    entered.set()
    assert release.wait(8)
    return 0


@event.listens_for(db.engine.sync_engine, "connect")
def install_function(connection, record):
    connection.create_function("probe_pause_writer", 0, pause_writer)


async def write():
    async with db.SessionLocal() as session:
        await session.execute(
            text(
                "INSERT OR REPLACE INTO runtime_sentinels (name, value) "
                "VALUES ('probe_cancel_pressure', '1') RETURNING probe_pause_writer()"
            )
        )
        await session.commit()


@app.post("/__probe/cancel-driver")
async def start():
    global owner, cancel_observed
    assert owner is None or owner.done()
    entered.clear()
    release.clear()
    owner = asyncio.create_task(write())
    assert await asyncio.to_thread(entered.wait, 3)
    owner.cancel()
    await asyncio.sleep(0.05)
    cancel_observed = not owner.done()
    # Give bridge completion/persistence time to reach the held writer slot.
    asyncio.get_running_loop().call_later(0.8, release.set)
    return {"native_statement_started": True, "cancellation_deferred": cancel_observed}


@app.post("/__probe/driver-result")
async def finish():
    assert owner is not None
    await asyncio.gather(owner, return_exceptions=True)
    path = sqlite_db_path_from_url(str(db.engine.url))

    def probe():
        connection = sqlite3.connect(path, timeout=0.25)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()
            return connection.execute(
                "SELECT count(*) FROM runtime_sentinels WHERE name = 'probe_cancel_pressure'"
            ).fetchone()[0]
        finally:
            connection.close()

    rows = await asyncio.to_thread(probe)
    return {"cancelled": owner.cancelled(), "writer_available": True, "rolled_back": rows == 0}
