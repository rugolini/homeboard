"""Prometheus text exposition of status.json, so Prometheus can keep long history and Grafana can chart it."""

HELP = {
    "homeboard_source_up": "1 when the source answered on the last collection",
    "homeboard_cpu_usage_percent": "Host CPU usage",
    "homeboard_cpu_temperature_celsius": "Host CPU package temperature",
    "homeboard_memory_used_bytes": "Host memory in use",
    "homeboard_memory_total_bytes": "Host memory total",
    "homeboard_disk_temperature_celsius": "Disk temperature (absent while spun down)",
    "homeboard_disk_spinning": "1 when the disk is spinning",
    "homeboard_disk_healthy": "1 when the disk reports no errors",
    "homeboard_disk_used_bytes": "Filesystem bytes used",
    "homeboard_disk_size_bytes": "Filesystem size",
    "homeboard_uplink_up": "1 when the uplink reaches the internet",
    "homeboard_uplink_active": "1 for the uplink carrying traffic",
    "homeboard_wan_rate_bits_per_second": "Current WAN throughput on the active uplink",
    "homeboard_wifi_clients": "Wi-Fi clients associated",
    "homeboard_modem_rsrp_dbm": "Mobile modem RSRP",
    "homeboard_modem_sinr_db": "Mobile modem SINR",
    "homeboard_vpn_peers_active": "WireGuard peers with a recent handshake",
    "homeboard_probe_up": "1 when the HTTP probe answered",
    "homeboard_probe_latency_seconds": "HTTP probe response time",
    "homeboard_status_page_up": "1 unless the provider reports a major outage",
    "homeboard_status_page_degraded": "1 when the provider reports a minor incident",
    "homeboard_ai_spend_month_usd": "Month-to-date AI spend",
    "homeboard_ai_spend_month_usd_by_tier": "Month-to-date AI spend per model tier",
    "homeboard_backup_ok": "1 when the last backup succeeded",
    "homeboard_backup_age_seconds": "Seconds since the last backup",
    "homeboard_agent_sessions_today": "Agent sessions started today",
    "homeboard_agent_tool_calls_today": "Agent tool calls today",
    "homeboard_subscriptions_monthly_brl": "Known monthly subscription costs",
    "homeboard_devices_online": "Catalog devices seen on DHCP",
    "homeboard_device_traffic_bits_per_second": "Traffic of a catalog device, from router counters",
    "homeboard_group_traffic_bits_per_second": "Traffic of a device group (personal, iot)",
    "homeboard_month_total_brl": "Subscriptions plus AI usage this month, in BRL",
    "homeboard_usd_brl": "USD/BRL exchange rate used (PTAX)",
}


def _num(value):
    return str(int(value)) if float(value).is_integer() else repr(round(float(value), 6))


def _esc(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def metrics(status):
    samples = {}

    def put(name, value, **labels):
        if value is None:
            return
        if isinstance(value, bool):
            value = int(value)
        label = ",".join(f'{k}="{_esc(v)}"' for k, v in labels.items())
        samples.setdefault(name, []).append(f"{name}{{{label}}} {_num(value)}" if label else f"{name} {_num(value)}")

    blocks = status.get("blocks", {})
    for source, block in blocks.items():
        put("homeboard_source_up", block.get("ok", False), source=source)
    data = {name: b["data"] for name, b in blocks.items() if b.get("ok")}

    if srv := data.get("server"):
        put("homeboard_cpu_usage_percent", srv.get("cpu_pct"))
        put("homeboard_cpu_temperature_celsius", srv.get("cpu_temp_c"))
        put("homeboard_memory_used_bytes", srv.get("memory", {}).get("used_bytes"))
        put("homeboard_memory_total_bytes", srv.get("memory", {}).get("total_bytes"))
        for d in srv.get("disks", []):
            put("homeboard_disk_temperature_celsius", d.get("temp_c"), disk=d["name"])
            put("homeboard_disk_spinning", d.get("spinning"), disk=d["name"])
            put("homeboard_disk_healthy", d.get("healthy"), disk=d["name"])
            put("homeboard_disk_used_bytes", d.get("used_bytes"), disk=d["name"])
            put("homeboard_disk_size_bytes", d.get("size_bytes"), disk=d["name"])
    if r := data.get("router"):
        for name, up in r.get("uplinks", {}).items():
            put("homeboard_uplink_up", up, uplink=name)
            put("homeboard_uplink_active", r.get("active") == name, uplink=name)
        for direction, mbps in (r.get("rate_mbps") or {}).items():
            put("homeboard_wan_rate_bits_per_second", round(mbps * 1e6), direction=direction)
        put("homeboard_wifi_clients", r.get("wifi_clients"))
        put("homeboard_modem_rsrp_dbm", (r.get("modem") or {}).get("rsrp"))
        put("homeboard_modem_sinr_db", (r.get("modem") or {}).get("sinr"))
        put("homeboard_vpn_peers_active", (r.get("vpn") or {}).get("active"))
    for host, p in (data.get("probes") or {}).items():
        put("homeboard_probe_up", p.get("ok"), host=host)
        put("homeboard_probe_latency_seconds", p["ms"] / 1000 if p.get("ms") is not None else None, host=host)
    for name, page in (data.get("status_pages") or {}).items():
        put("homeboard_status_page_up", page.get("up"), page=name)
        put("homeboard_status_page_degraded", page.get("degraded"), page=name)
    if ai := data.get("ai_spend"):
        put("homeboard_ai_spend_month_usd", ai.get("month_usd"))
        for tier, usd in ai.get("by_tier", {}).items():
            put("homeboard_ai_spend_month_usd_by_tier", usd, tier=tier)
    if bk := data.get("backup"):
        put("homeboard_backup_ok", bk.get("ok"))
        put("homeboard_backup_age_seconds", round(bk["age_hours"] * 3600) if bk.get("age_hours") is not None else None)
    if agent := data.get("agent"):
        put("homeboard_agent_sessions_today", agent.get("sessions_today"))
        put("homeboard_agent_tool_calls_today", agent.get("tool_calls_today"))
    put("homeboard_subscriptions_monthly_brl", status.get("catalog", {}).get("costs", {}).get("total_brl"))
    put("homeboard_month_total_brl", (status.get("costs") or {}).get("total_brl"))
    put("homeboard_usd_brl", ((status.get("costs") or {}).get("fx") or {}).get("usd_brl"))
    devices = status.get("devices") or {}
    for group, items in devices.items():
        if group in ("unknown", "traffic"):
            continue
        put("homeboard_devices_online", sum(1 for d in items if d.get("online")), group=group)
        for d in items:
            for direction in ("down", "up"):
                mbps = d.get(f"{direction}_mbps")
                put("homeboard_device_traffic_bits_per_second", round(mbps * 1e6) if mbps is not None else None,
                    device=d["name"], direction=direction)
    for group, rates in (devices.get("traffic") or {}).items():
        for direction in ("down", "up"):
            put("homeboard_group_traffic_bits_per_second", round(rates[f"{direction}_mbps"] * 1e6), group=group, direction=direction)

    lines = []
    for name, rows in samples.items():
        lines += [f"# HELP {name} {HELP.get(name, name)}", f"# TYPE {name} gauge", *rows]
    return "\n".join(lines) + "\n"
