"""Atlassian Statuspage /api/v2/status.json summary (used by Claude, Cloudflare, GitHub and many others)."""


def statuspage(page):
    status = page.get("status", {})
    indicator = status.get("indicator", "none")
    return {"up": indicator not in ("major", "critical"), "degraded": indicator == "minor",
            "description": status.get("description")}
