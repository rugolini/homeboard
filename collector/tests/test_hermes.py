import datetime as dt
import sqlite3
import unittest

from homeboard.hermes import summary

NOW = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)
TODAY = NOW.timestamp() - 3600
YESTERDAY = NOW.timestamp() - 86400 * 2


def db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        create table sessions (id text primary key, source text, title text, started_at real, ended_at real,
            tool_call_count integer, estimated_cost_usd real, actual_cost_usd real, archived integer default 0);
        create table messages (id integer primary key autoincrement, session_id text, role text, content text,
            tool_name text, tool_calls text, timestamp real, active integer default 1);
    """)
    conn.executemany("insert into sessions values (?,?,?,?,?,?,?,?,0)", [
        ("old", "cron", "old", YESTERDAY, YESTERDAY + 60, 9, 0.5, None),
        ("s1", "whatsapp", "Media server slow?", TODAY, None, 3, 0.02, 0.03),
    ])
    conn.executemany("insert into messages (session_id, role, content, tool_name, tool_calls, timestamp) values (?,?,?,?,?,?)", [
        ("old", "user", "old thing", None, None, YESTERDAY),
        ("s1", "user", "is the media server slow?", None, None, TODAY + 1),
        ("s1", "assistant", "Measuring before changing anything.", None, '[{"function":{"name":"terminal"}}]', TODAY + 2),
        ("s1", "tool", "CPU 4% token=sk-abcdefghijklmnopqrstuv", "terminal", None, TODAY + 3),
        ("s1", "tool", "ok", "browser_navigate", None, TODAY + 4),
        ("s1", "tool", "x" * 500, "terminal", None, TODAY + 5),
    ])
    return conn


class HermesTest(unittest.TestCase):
    def test_counts_today_only(self):
        s = summary(db(), NOW)
        self.assertEqual((s["sessions_today"], s["tool_calls_today"]), (1, 3))

    def test_cost_prefers_actual_over_estimated(self):
        self.assertEqual(summary(db(), NOW)["cost_today_usd"], 0.03)

    def test_top_tools_today(self):
        self.assertEqual(summary(db(), NOW)["top_tools"], [["terminal", 2], ["browser_navigate", 1]])

    def test_last_session_steps_in_order_with_kinds(self):
        steps = summary(db(), NOW)["last_session"]["steps"]
        self.assertEqual([s["kind"] for s in steps], ["request", "thought", "tool", "tool", "tool"])
        self.assertEqual(steps[2]["tool"], "terminal")

    def test_steps_redact_secrets_and_truncate(self):
        steps = summary(db(), NOW)["last_session"]["steps"]
        self.assertNotIn("sk-abc", steps[2]["text"])
        self.assertIn("[secret]", steps[2]["text"])
        self.assertLessEqual(len(steps[4]["text"]), 161)

    def test_json_tool_output_becomes_a_short_summary(self):
        conn = db()
        conn.execute("insert into messages (session_id, role, content, tool_name, timestamp) values (?,?,?,?,?)",
                     ("s1", "tool", '{"status": "success", "output": "3 files written\\nmore detail", "duration": 1.2}',
                      "execute_code", TODAY + 6))
        last = summary(conn, NOW)["last_session"]["steps"][-1]
        self.assertEqual(last["text"], "success · 3 files written")

    def test_json_tool_error_is_shown_first(self):
        conn = db()
        conn.execute("insert into messages (session_id, role, content, tool_name, timestamp) values (?,?,?,?,?)",
                     ("s1", "tool", '{"output": "", "error": "permission denied"}', "terminal", TODAY + 6))
        self.assertEqual(summary(conn, NOW)["last_session"]["steps"][-1]["text"], "error: permission denied")

    def test_last_session_title_and_running_state(self):
        last = summary(db(), NOW)["last_session"]
        self.assertEqual((last["title"], last["running"]), ("Media server slow?", True))


if __name__ == "__main__":
    unittest.main()
