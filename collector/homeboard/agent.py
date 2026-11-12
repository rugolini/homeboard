"""What the agent is doing, did and changed, from a copy of a Hermes state.db.

Sessions rarely close and seldom get a title, so activity is read from message timestamps and the first request.
"""
import json
import re

from .hermes import _clean

ACTIVE_SECONDS = 120
DIARY_DAYS = 7
MAX_DIARY = 12
MAX_CHANGES = 15
# Commands that change state somewhere; read-only ones (ls, cat, grep...) are not "changes".
_CHANGE = re.compile(r"\b(docker (restart|rm|stop|start|compose|pull|run|kill|update)|systemctl|rm |mv |cp |sed -i|tee |"
                     r"chmod|chown|uci (set|commit|delete)|git (push|commit)|apt |pip install|kill |reboot|tar x|"
                     r"curl .*-X ?(POST|PUT|DELETE|PATCH))")
_EDIT_TOOLS = ("write_file", "patch")
_SCRATCH = ("/tmp/", "/var/tmp/")


def _is_error(content):
    try:
        data = json.loads(content or "")
    except ValueError:
        return False
    return isinstance(data, dict) and bool(data.get("error"))


def _sessions(conn, since):
    rows = conn.execute(
        "select s.id, s.source, s.title, min(m.timestamp), max(m.timestamp), "
        "sum(m.role = 'tool'), (select content from messages u where u.session_id = s.id and u.role = 'user' "
        "order by u.timestamp limit 1) from sessions s join messages m on m.session_id = s.id "
        "where s.parent_session_id is null and s.archived = 0 and m.active = 1 group by s.id "
        "having max(m.timestamp) >= ? order by min(m.timestamp) desc", (since,)).fetchall()
    out = []
    for sid, source, title, first, last, tools, request in rows:
        errors = sum(_is_error(c) for (c,) in conn.execute(
            "select content from messages where session_id = ? and role = 'tool'", (sid,)))
        out.append({"id": sid, "source": source, "title": _clean(title or request or "") or None, "first": first,
                    "last": last, "minutes": round((last - first) / 60), "tool_calls": tools or 0, "errors": errors})
    return out


def _changes(conn, since):
    out = []
    for ts, calls in conn.execute("select timestamp, tool_calls from messages where role = 'assistant' "
                                  "and tool_calls is not null and timestamp >= ? order by timestamp desc", (since,)):
        try:
            items = json.loads(calls)
        except ValueError:
            continue
        for item in items:
            fn = item.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            if fn.get("name") in _EDIT_TOOLS and args.get("path") and not args["path"].startswith(_SCRATCH):
                out.append({"time": ts, "kind": "file", "text": _clean(args["path"])})
            elif fn.get("name") == "terminal" and _CHANGE.search(args.get("command", "")):
                out.append({"time": ts, "kind": "command", "text": _clean(args["command"])})
    return out[:MAX_CHANGES]


def activity(conn, now):
    ts = now.timestamp()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    diary = _sessions(conn, ts - DIARY_DAYS * 86400)
    latest = max(diary, key=lambda d: d["last"], default=None)
    tool_rows = conn.execute("select tool_name, content from messages where role = 'tool' and timestamp >= ?",
                             (today,)).fetchall()
    errors = {}
    for tool, content in tool_rows:
        if _is_error(content):
            errors[tool] = errors.get(tool, 0) + 1
    inp, cached = conn.execute("select coalesce(sum(input_tokens),0), coalesce(sum(cache_read_tokens),0) from sessions "
                               "where parent_session_id is null and started_at >= ?", (today,)).fetchone()
    return {
        "now": latest and {
            "active": ts - latest["last"] <= ACTIVE_SECONDS, "title": latest["title"], "source": latest["source"],
            "minutes": latest["minutes"], "steps": latest["tool_calls"], "idle_minutes": round((ts - latest["last"]) / 60),
        },
        "diary": diary[:MAX_DIARY],
        "health": {
            "tool_calls_today": len(tool_rows),
            "tool_errors_today": sum(errors.values()),
            "errors_by_tool": sorted(([k, v] for k, v in errors.items()), key=lambda kv: -kv[1])[:5],
            "cache_pct": round(100 * cached / (inp + cached), 1) if inp + cached else None,
        },
        "changes": _changes(conn, ts - DIARY_DAYS * 86400),
    }


def attribute_costs(diary, requests, grace=60):
    """Gateway spend per session: requests of the agent's key that fall inside the session's message window."""
    priced = []
    for d in diary:
        cost = sum(usd for t, usd in requests if d["first"] - grace <= t <= d["last"] + grace)
        priced.append({**d, "cost_usd": round(cost, 4)})
    return priced
