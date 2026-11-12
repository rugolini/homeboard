import datetime as dt
import json
import sqlite3
import unittest

from homeboard.agent import activity, attribute_costs

NOW = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)
T = NOW.timestamp()


def call(name, **args):
    return json.dumps([{"type": "function", "function": {"name": name, "arguments": json.dumps(args)}}])


def db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        create table sessions (id text primary key, source text, title text, started_at real, ended_at real,
            parent_session_id text, model text, input_tokens integer, cache_read_tokens integer, archived integer default 0);
        create table messages (id integer primary key autoincrement, session_id text, role text, content text,
            tool_name text, tool_calls text, timestamp real, active integer default 1);
    """)
    conn.executemany("insert into sessions values (?,?,?,?,?,?,?,?,?,0)", [
        ("a", "whatsapp", None, T - 3000, None, None, "coordenacao", 1000, 3000),
        ("b", "cron", "Revisão semanal", T - 600, None, None, "coordenacao", 500, 500),
        ("sub", "subagent", None, T - 500, None, "b", "tarefas", 10, 0),
        ("old", "cli", None, T - 86400 * 9, None, None, "x", 1, 0),
    ])
    rows = [
        ("a", "user", "analisa este vídeo token=sk-abcdefghijklmnopqrst", None, None, T - 3000),
        ("a", "assistant", "", None, call("terminal", command="ssh unraid-host docker restart searxng"), T - 2990),
        ("a", "tool", '{"output": "searxng"}', "terminal", None, T - 2980),
        ("a", "assistant", "", None, call("write_file", path="/opt/data/workspace/home-network/caddy/Caddyfile", content="x"), T - 2970),
        ("a", "tool", '{"error": "permission denied"}', "write_file", None, T - 2960),
        ("a", "assistant", "", None, call("terminal", command="ls -la /tmp"), T - 2950),
        ("a", "tool", '{"output": "ok"}', "terminal", None, T - 2400),
        ("a", "assistant", "", None, call("write_file", path="/tmp/x/scratch.json", content="x"), T - 2390),
        ("b", "user", "rode a revisão semanal", None, None, T - 600),
        ("b", "tool", '{"output": "ok"}', "terminal", None, T - 60),
        ("old", "user", "coisa antiga", None, None, T - 86400 * 9),
    ]
    conn.executemany("insert into messages (session_id, role, content, tool_name, tool_calls, timestamp) values (?,?,?,?,?,?)", rows)
    return conn


class NowTest(unittest.TestCase):
    def test_latest_session_with_recent_messages_is_active(self):
        now = activity(db(), NOW)["now"]
        self.assertEqual((now["active"], now["title"], now["source"]), (True, "Revisão semanal", "cron"))
        self.assertEqual(now["minutes"], 9)

    def test_idle_when_last_message_is_old(self):
        later = NOW + dt.timedelta(minutes=30)
        now = activity(db(), later)["now"]
        self.assertFalse(now["active"])
        self.assertEqual(now["idle_minutes"], 31)


class DiaryTest(unittest.TestCase):
    def test_top_level_sessions_of_the_last_week_newest_first(self):
        diary = activity(db(), NOW)["diary"]
        self.assertEqual([d["id"] for d in diary], ["b", "a"])

    def test_title_falls_back_to_the_first_request_redacted(self):
        a = activity(db(), NOW)["diary"][1]
        self.assertEqual(a["title"], "analisa este vídeo token=[secret]")

    def test_duration_tools_and_errors(self):
        a = activity(db(), NOW)["diary"][1]
        self.assertEqual((a["minutes"], a["tool_calls"], a["errors"]), (10, 3, 1))


class HealthTest(unittest.TestCase):
    def test_tool_errors_today_by_tool(self):
        health = activity(db(), NOW)["health"]
        self.assertEqual(health["tool_calls_today"], 4)
        self.assertEqual(health["tool_errors_today"], 1)
        self.assertEqual(health["errors_by_tool"], [["write_file", 1]])

    def test_cache_share_of_input_today(self):
        self.assertEqual(activity(db(), NOW)["health"]["cache_pct"], 70.0)


class ChangesTest(unittest.TestCase):
    def test_scratch_files_in_tmp_are_not_changes(self):
        self.assertNotIn("/tmp/x/scratch.json", [c["text"] for c in activity(db(), NOW)["changes"]])

    def test_file_edits_and_state_changing_commands_only(self):
        changes = activity(db(), NOW)["changes"]
        self.assertEqual([c["kind"] for c in changes], ["file", "command"])
        self.assertEqual(changes[0]["text"], "/opt/data/workspace/home-network/caddy/Caddyfile")
        self.assertEqual(changes[1]["text"], "ssh unraid-host docker restart searxng")


class CostsTest(unittest.TestCase):
    def test_request_spend_is_attributed_to_the_session_window(self):
        diary = activity(db(), NOW)["diary"]
        requests = [(T - 2995, 0.01), (T - 2500, 0.02), (T - 300, 0.05), (T - 86400, 9.0)]
        priced = attribute_costs(diary, requests)
        self.assertEqual({d["id"]: d["cost_usd"] for d in priced}, {"b": 0.05, "a": 0.03})


if __name__ == "__main__":
    unittest.main()
