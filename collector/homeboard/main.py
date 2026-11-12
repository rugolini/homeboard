"""Collector loop: every interval, read all sources, update availability history and write status.json."""
import functools
import http.server
import json
import os
import pathlib
import sys
import threading
import time

from . import catalog, config, sources
from .build import apps, build
from .history import History


def collect(cfg, state, history):
    src, now = cfg["sources"], sources.now_local(cfg["site"].get("timezone", "UTC"))
    fetchers = {}
    if "unraid" in src:
        fetchers["server"] = lambda: sources.unraid(src["unraid"], state)
    if "docker" in src:
        fetchers["containers"] = lambda: sources.containers(src["docker"])
    if "backup" in src:
        fetchers["backup"] = lambda: sources.backup(src["backup"], now)
    if "glinet" in src:
        fetchers["router"] = lambda: sources.glinet(src["glinet"], state)
    if "litellm" in src:
        fetchers["ai_spend"] = lambda: sources.litellm(src["litellm"], now)
    if "hermes" in src:
        fetchers["agent"] = lambda: sources.hermes(src["hermes"], now)
    if "adguard" in src:
        fetchers["dns"] = lambda: sources.adguard(src["adguard"])
    fetchers["probes"] = lambda: {p["host"]: sources.probe(p["url"]) for p in cfg["probe"]}

    status = build(fetchers, now)
    blocks = status["blocks"]
    probes = blocks["probes"].get("data", {})
    for host, result in probes.items():
        history.record(f"app:{host}", result["ok"], now)
    router = blocks.get("router", {})
    if router.get("ok"):
        for name, up in router["data"]["uplinks"].items():
            history.record(f"uplink:{name}", up, now)

    text = cfg["raw_text"]
    containers = blocks.get("containers", {}).get("data", [])
    status["site"] = cfg["site"]
    status["map"] = cfg["map"]
    status["catalog"] = catalog.load(text)
    status["apps"] = apps(text, containers, probes)
    leases = router["data"]["leases"] if router.get("ok") else []
    status["devices"] = catalog.devices(text, leases)
    today = now.date()
    status["history"] = {c: {"uptime_pct": history.uptime(c, today), "downtime_min": history.downtime_minutes(c, today),
                             "daily": history.daily(c, today)} for c in history.to_dict()}
    return status


def _write_json(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, default=str))
    tmp.replace(path)


def serve(web_dir, data_dir, port):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            if path.split("?")[0] == "/status.json":
                return str(pathlib.Path(data_dir) / "status.json")
            return super().translate_path(path)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), functools.partial(Handler, directory=web_dir))
    threading.Thread(target=server.serve_forever, daemon=True).start()


def main():
    cfg = config.parse(pathlib.Path(os.environ.get("HOMEBOARD_CONFIG", "/config/homeboard.toml")).read_text())
    data = pathlib.Path(cfg["collector"]["data_dir"])
    data.mkdir(parents=True, exist_ok=True)
    hist_file = data / "history.json"
    history = History.from_dict(json.loads(hist_file.read_text())) if hist_file.exists() else History()
    serve(cfg["collector"]["web_dir"], data, cfg["collector"]["port"])
    state = {}
    while True:
        started = time.monotonic()
        try:
            _write_json(data / "status.json", collect(cfg, state, history))
            _write_json(hist_file, history.to_dict())
        except Exception as exc:  # keep serving the last good status
            print(f"collect failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        time.sleep(max(1, cfg["collector"]["interval_seconds"] - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
