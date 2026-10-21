import sqlite3

import tools.storage as storage


def test_record_run(isolated_db):
    storage.init_db()
    storage.record_run("2026-10-20T16:30:00-04:00", "ok")
    rows = sqlite3.connect(isolated_db).execute("SELECT run_ts, status, note FROM runs").fetchall()
    assert rows == [("2026-10-20T16:30:00-04:00", "ok", None)]
