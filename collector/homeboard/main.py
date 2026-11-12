"""Collector loop: the router every fast interval (live traffic), everything else every interval; writes status.json."""
import functools
import http.server
import json
import os
import pathlib
import sys
import threading
import time

from . import catalog, config, sources
from .metrics import metrics
from .costs import breakdown
from .agent import attribute_costs
from .destinations import by_service
from .build import apps, build
from .history import History


FAST_SOURCES = {"router"}


def collect(cfg, state, history, slow=True):
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
    if "fx" in src:
        fetchers["fx"] = lambda: sources.fx(state, now)
    mapped = [svc for cat in catalog.load(cfg["raw_text"])["categories"].values() for svc in cat
              if svc.get("asn") or svc.get("ip_ranges")]
    if mapped:
        fetchers["prefixes"] = lambda: sources.prefixes(mapped, state, now)
    if cfg["statuspage"]:
        fetchers["status_pages"] = lambda: sources.statuspages(cfg["statuspage"])
    fetchers["probes"] = lambda: {p["host"]: sources.probe(p["url"], p.get("insecure", False)) for p in cfg["probe"]}

    if not slow:
        fetchers = {k: v for k, v in fetchers.items() if k in FAST_SOURCES}
    status = build(fetchers, now)
    # Blocks not refreshed on a fast tick keep their last value.
    state["blocks"] = blocks = {**state.get("blocks", {}), **status["blocks"]}
    status["blocks"] = blocks
    probes = blocks.get("probes", {}).get("data", {})
    router = blocks.get("router", {})
    if slow:  # uptime math assumes one sample per minute
        for host, result in probes.items():
            history.record(f"app:{host}", result["ok"], now)
        for name, page in blocks.get("status_pages", {}).get("data", {}).items():
            if page["up"] is not None:
                history.record(f"page:{name}", page["up"], now)
        if router.get("ok"):
            for name, up in router["data"]["uplinks"].items():
                history.record(f"uplink:{name}", up, now)

    text = cfg["raw_text"]
    containers = blocks.get("containers", {}).get("data", [])
    status["site"] = cfg["site"]
    status["map"] = cfg["map"]
    status["agent_key"] = src.get("hermes", {}).get("litellm_key")
    status["agent_name"] = src.get("hermes", {}).get("display_name", "Hermes")
    spend_block = blocks.get("ai_spend", {})
    agent_block = blocks.get("agent", {})
    if spend_block.get("ok") and (spend_block["data"].get("agent") or {}).get("requests") is not None:
        agent_spend = spend_block["data"]["agent"]
        if agent_block.get("ok") and agent_block["data"].get("activity"):
            act = agent_block["data"]["activity"]
            status["agent_activity"] = {**act, "diary": attribute_costs(act["diary"], agent_spend["requests"])}
        status["agent_budget"] = agent_spend.get("budget")
        # The raw request list is only for attribution; keep status.json small.
        status["blocks"] = {**blocks, "ai_spend": {**spend_block, "data": {k: v for k, v in spend_block["data"].items() if k != "agent"}}}
    elif agent_block.get("ok"):
        status["agent_activity"] = agent_block["data"].get("activity")
    status["catalog"] = catalog.load(text)
    status["costs"] = breakdown(status["catalog"], blocks.get("ai_spend", {}).get("data"), blocks.get("fx", {}).get("data"))
    status["apps"] = apps(text, containers, probes)
    leases = router["data"]["leases"] if router.get("ok") else []
    clients = router["data"].get("clients", []) if router.get("ok") else []
    traffic = {c["name"]: (c["down_mbps"], c["up_mbps"]) for c in clients}
    status["devices"] = catalog.devices(text, leases + list(traffic), traffic)
    nets = blocks.get("prefixes", {}).get("data") or {}
    status["service_traffic"] = by_service(router["data"].get("ct"), nets) if router.get("ok") and nets else {}
    # Prefix lists are big and only needed here.
    status["blocks"] = {**status["blocks"], **({"prefixes": {"ok": blocks["prefixes"]["ok"], "data": {k: len(v) for k, v in nets.items()}}}
                                                if "prefixes" in blocks else {})}
    if router.get("ok"):
        status["blocks"]["router"] = {**router, "data": {k: v for k, v in router["data"].items() if k != "ct"}}
    server_host = src.get("glinet", {}).get("server_client")
    status["server_traffic"] = dict(zip(("down_mbps", "up_mbps"), traffic[server_host])) if server_host in traffic else None
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
        def do_GET(self):
            if self.path.split("?")[0] != "/metrics":
                return super().do_GET()
            try:
                body = metrics(json.loads((pathlib.Path(data_dir) / "status.json").read_text())).encode()
            except (OSError, ValueError):
                self.send_error(503, "no status yet")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
    state, last_slow = {}, 0.0
    fast, slow_every = cfg["collector"]["fast_interval_seconds"], cfg["collector"]["interval_seconds"]
    while True:
        started = time.monotonic()
        slow = started - last_slow >= slow_every
        try:
            _write_json(data / "status.json", collect(cfg, state, history, slow=slow))
            if slow:
                last_slow = started
                _write_json(hist_file, history.to_dict())
        except Exception as exc:  # keep serving the last good status
            print(f"collect failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        time.sleep(max(1, fast - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
