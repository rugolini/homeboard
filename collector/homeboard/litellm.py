"""Month-to-date AI spend from LiteLLM_SpendLogs, grouped by a configurable model_group -> tier map."""


def spend(daily_rows, key_rows, tiers=None):
    tiers = tiers or {}
    by_tier = {t: 0.0 for t in dict.fromkeys(tiers.values())}
    by_tier["other"] = 0.0
    days = {}
    for day, group, usd in daily_rows:
        tier = tiers.get(group, "other")
        by_tier[tier] += usd
        bucket = days.setdefault(day.isoformat(), {"day": day.isoformat()})
        bucket[tier] = round(bucket.get(tier, 0) + usd, 4)
    return {
        "month_usd": round(sum(by_tier.values()), 4),
        "by_tier": {t: round(v, 4) for t, v in by_tier.items()},
        "daily": [days[d] for d in sorted(days)],
        "by_key": [[name or "unnamed", round(usd, 4)] for name, usd in key_rows],
    }
