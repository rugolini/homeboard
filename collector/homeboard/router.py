"""Parser for the JSON printed by adapters/gl-inet/homeboard-status.sh.

uplinks: [{"dev": "pppoe-wan", "name": "fiber", "probe": "fiber_ok"}, ...] from the config.
"""
# WireGuard renegotiates every ~2 min while traffic flows; older handshakes mean an idle peer.
VPN_ACTIVE_SECONDS = 180


def router(status, uplinks, previous=None):
    by_dev = {u["dev"]: u for u in uplinks}
    routes = sorted((r for r in status.get("routes", []) if r["dev"] in by_dev), key=lambda r: r["metric"])
    active_dev = next((r["dev"] for r in routes if status.get(by_dev[r["dev"]]["probe"])), None)
    handshakes = status.get("wg_handshakes", [])
    modem = status.get("modem") or {}
    return {
        "active": by_dev[active_dev]["name"] if active_dev else None,
        "uplinks": {u["name"]: bool(status.get(u["probe"])) for u in uplinks},
        "wan_uptime_s": status.get("wan_uptime"),
        "rate_mbps": _rate(status, previous, active_dev),
        "modem": {"rsrp": modem.get("rsrp"), "sinr": modem.get("sinr"), "type": modem.get("network_type")},
        "vpn": {
            "peers": len(handshakes),
            "active": sum(1 for h in handshakes if h and status["time"] - h < VPN_ACTIVE_SECONDS),
            "last_handshake": max(handshakes, default=0) or None,
        },
        "wifi_clients": sum(n for radio, n in status.get("assoc", {}).items() if not radio.startswith("apcli")),
        "leases": status.get("leases", []),
    }


def _rate(status, previous, dev):
    if not previous or not dev or dev not in status.get("counters", {}) or dev not in previous.get("counters", {}):
        return None
    seconds = status["time"] - previous["time"]
    rx = status["counters"][dev][0] - previous["counters"][dev][0]
    tx = status["counters"][dev][1] - previous["counters"][dev][1]
    if seconds <= 0 or rx < 0 or tx < 0:
        return None
    return {"down": round(rx * 8 / seconds / 1e6, 1), "up": round(tx * 8 / seconds / 1e6, 1)}
