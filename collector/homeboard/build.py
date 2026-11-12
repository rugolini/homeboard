"""Assembles status.json: one block per source, a failing source never takes the others down."""
import json
import tomllib

STALE_BACKUP_HOURS = 26


def build(sources, now):
    blocks = {}
    for name, fetch in sources.items():
        try:
            blocks[name] = {"ok": True, "data": fetch()}
        except Exception as exc:  # a failing source shows as unavailable on the page
            blocks[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"generated_at": now.isoformat(), "blocks": blocks}


def apps(catalog_text, containers, probes):
    states = {n.lstrip("/"): c.get("State") for c in containers for n in c.get("Names", [])}
    out = []
    for app in tomllib.loads(catalog_text).get("app", []):
        host, container = app.get("host"), app.get("container")
        probe = probes.get(host) if host else None
        if container and container not in states:
            state = "down"
        elif container and states[container] != "running":
            # A stopped (not removed) container was paused on purpose.
            state = "paused"
        elif probe is not None and not probe["ok"]:
            state = "down"
        else:
            state = "up"
        out.append({"label": app["label"], "host": host, "state": state, "ms": probe["ms"] if probe else None,
                    **({"icon": app["icon"]} if "icon" in app else {})})
    return out


def backup(text, now):
    status = json.loads(text)
    age = (now.timestamp() - status["time"]) / 3600
    return {
        "ok": bool(status.get("ok")),
        "age_hours": round(age, 1),
        "seconds": status.get("seconds"),
        "stale": age > STALE_BACKUP_HOURS,
        "error": status.get("error"),
    }
