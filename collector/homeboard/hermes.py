"""Summary of what Hermes did today, read from a copy of its state.db."""
import json
import re

MAX_TEXT = 160
MAX_STEPS = 8
# Tokens and keys must never reach the page, even truncated.
_SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{16,}|eyJ[A-Za-z0-9_-]{20,}|[A-Fa-f0-9]{32,})")
_KIND = {"user": "request", "assistant": "thought", "tool": "tool"}


def _clean(text):
    text = _SECRET.sub("[secret]", " ".join((text or "").split()))
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 1] + "…"


_SUMMARY_KEYS = ("status", "output", "content", "result", "message", "path")


def _tool_text(content):
    """Tools answer in JSON; show the error or status and the first line of output instead of the raw object."""
    try:
        data = json.loads(content or "")
    except ValueError:
        return content
    if not isinstance(data, dict):
        return content
    if data.get("error"):
        return f"error: {data['error']}"
    parts = []
    for key in _SUMMARY_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip().splitlines()[0])
        if len(parts) == 2:
            break
    return " · ".join(parts) or content


def summary(conn, now):
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    sessions, tools, cost = conn.execute(
        "select count(*), coalesce(sum(tool_call_count),0), coalesce(sum(coalesce(actual_cost_usd, estimated_cost_usd)),0) "
        "from sessions where started_at >= ? and archived = 0", (start,)).fetchone()
    top = conn.execute(
        "select tool_name, count(*) from messages where role='tool' and tool_name is not null and timestamp >= ? "
        "group by tool_name order by 2 desc, 1 limit 5", (start,)).fetchall()
    return {
        "sessions_today": sessions,
        "tool_calls_today": tools,
        "cost_today_usd": round(cost, 4),
        "top_tools": [list(t) for t in top],
        "last_session": _last_session(conn),
    }


def _last_session(conn):
    row = conn.execute("select id, title, started_at, ended_at from sessions where archived = 0 "
                       "order by started_at desc limit 1").fetchone()
    if not row:
        return None
    sid, title, started, ended = row
    msgs = conn.execute("select role, content, tool_name from messages where session_id = ? and active = 1 "
                        "and role in ('user','assistant','tool') order by timestamp desc, id desc limit ?",
                        (sid, MAX_STEPS * 2)).fetchall()
    steps = []
    for role, content, tool in reversed(msgs):
        if role == "assistant" and not (content or "").strip():
            continue
        step = {"kind": _KIND[role], "text": _clean(_tool_text(content) if role == "tool" else content)}
        if tool:
            step["tool"] = tool
        steps.append(step)
    return {"title": title, "started_at": started, "running": ended is None, "steps": steps[-MAX_STEPS:]}
