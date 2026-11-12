"""Docker /containers/<name>/stats?stream=false summary."""


def container_stats(stats):
    cpu, pre = stats.get("cpu_stats", {}), stats.get("precpu_stats", {})
    used, before = cpu.get("cpu_usage", {}).get("total_usage"), pre.get("cpu_usage", {}).get("total_usage")
    system, system_before = cpu.get("system_cpu_usage"), pre.get("system_cpu_usage")
    cpu_pct = None
    if None not in (used, before, system, system_before) and system > system_before:
        cpu_pct = round((used - before) / (system - system_before) * cpu.get("online_cpus", 1) * 100, 1)
    mem = stats.get("memory_stats", {})
    nets = (stats.get("networks") or {}).values()
    return {
        "cpu_pct": cpu_pct,
        # Page cache the kernel can drop is not memory the app holds.
        "mem_bytes": mem.get("usage", 0) - mem.get("stats", {}).get("inactive_file", 0),
        "mem_limit_bytes": mem.get("limit"),
        "net_rx_bytes": sum(n.get("rx_bytes", 0) for n in nets),
        "net_tx_bytes": sum(n.get("tx_bytes", 0) for n in nets),
        "pids": stats.get("pids_stats", {}).get("current"),
    }
