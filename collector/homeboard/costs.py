"""Month cost breakdown in BRL: fixed subscriptions plus AI usage converted at the day's PTAX rate."""


def ptax(response):
    """Banco Central do Brasil PTAX (CotacaoDolarPeriodo): the latest selling rate in the window."""
    rows = response.get("value") or []
    if not rows:
        return None
    last = max(rows, key=lambda r: r["dataHoraCotacao"])
    return {"usd_brl": last["cotacaoVenda"], "date": last["dataHoraCotacao"][:10]}


def breakdown(catalog, ai_spend, fx):
    rate = fx["usd_brl"] if fx else None
    by_cat = catalog["costs"]["by_category"]
    categories = [
        {"key": cat, "brl": round(by_cat[cat], 2),
         "items": [{"name": s["name"], "brl": s["monthly_brl"]} for s in items if s.get("monthly_brl")]}
        for cat, items in catalog["categories"].items() if by_cat.get(cat)
    ]
    subscriptions = {"key": "subscriptions", "brl": round(sum(c["brl"] for c in categories), 2), "children": categories}
    parts = [subscriptions]
    if ai_spend:
        tiers = [{"key": t, "usd": usd, "brl": round(usd * rate, 2) if rate else None}
                 for t, usd in ai_spend["by_tier"].items() if usd]
        usd = ai_spend["month_usd"]
        parts.append({"key": "ai_usage", "usd": usd, "brl": round(usd * rate, 2) if rate else None, "children": tiers})
    return {
        "total_brl": round(sum(p["brl"] for p in parts if p["brl"] is not None), 2),
        "parts": parts,
        "missing": catalog["costs"]["missing"],
        "fx": fx,
    }
