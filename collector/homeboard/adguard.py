"""AdGuard Home /control/stats summary."""


def adguard(stats):
    queries, blocked = stats.get("num_dns_queries", 0), stats.get("num_blocked_filtering", 0)
    avg = stats.get("avg_processing_time")
    return {
        "queries": queries,
        "blocked": blocked,
        "blocked_pct": round(100 * blocked / queries, 1) if queries else None,
        # AdGuard reports seconds.
        "avg_ms": round(avg * 1000, 1) if avg is not None else None,
    }
