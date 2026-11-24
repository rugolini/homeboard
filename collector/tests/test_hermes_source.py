import datetime as dt
import fcntl
import pathlib
import sqlite3
import tempfile
import threading
import time
import unittest

from homeboard import sources

NOW = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)


def copy_of_state_db(folder):
    """A state.db as the copier leaves it: database plus a write-ahead log holding the newest rows."""
    path = pathlib.Path(folder) / "state.db"
    conn = sqlite3.connect(path)
    conn.execute("pragma journal_mode=wal")
    conn.executescript("""
        create table sessions (id text primary key, source text, title text, started_at real, ended_at real,
            tool_call_count integer, estimated_cost_usd real, actual_cost_usd real, parent_session_id text, model text,
            input_tokens integer, cache_read_tokens integer, archived integer default 0);
        create table messages (id integer primary key autoincrement, session_id text, role text, content text,
            tool_name text, tool_calls text, timestamp real, active integer default 1);
    """)
    conn.execute("pragma wal_autocheckpoint=0")
    conn.execute("insert into sessions values ('s1','whatsapp','Media server slow?',?,null,3,0.02,null,null,'m',1,0,0)", (NOW.timestamp() - 60,))
    conn.commit()
    keep_wal = sqlite3.connect(path)  # an open reader stops the close below from folding the log into the database
    keep_wal.execute("select count(*) from sessions").fetchone()
    conn.close()
    return path, keep_wal


class HermesSourceTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.db, keep = copy_of_state_db(self.dir.name)
        self.addCleanup(keep.close)

    def test_reads_rows_that_are_still_in_the_write_ahead_log(self):
        self.assertTrue(self.db.with_name("state.db-wal").stat().st_size > 0)
        self.assertEqual(sources.hermes({"state_db": str(self.db)}, NOW)["sessions_today"], 1)

    def test_waits_while_the_copier_holds_the_lock(self):
        with open(self.db.with_name("state.db.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            done = []
            reader = threading.Thread(target=lambda: done.append(sources.hermes({"state_db": str(self.db)}, NOW)))
            reader.start()
            time.sleep(0.3)
            self.assertEqual(done, [], "read the database while the copier was writing it")
            fcntl.flock(lock, fcntl.LOCK_UN)
            reader.join(5)
        self.assertEqual(done[0]["sessions_today"], 1)

    def test_leaves_the_copy_untouched(self):
        before = self.db.read_bytes(), self.db.with_name("state.db-wal").read_bytes()
        sources.hermes({"state_db": str(self.db)}, NOW)
        self.assertEqual((self.db.read_bytes(), self.db.with_name("state.db-wal").read_bytes()), before)
