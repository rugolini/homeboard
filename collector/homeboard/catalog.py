"""Service catalog: the official list of what the house uses, grouped by category, with monthly costs."""
import tomllib

CATEGORIES = ("connection", "dns", "lan", "security", "code", "ai", "streaming", "cloud", "home", "access")
ROLES = ("active", "standby")


class CatalogError(ValueError):
    pass


def load(text):
    services = tomllib.loads(text).get("service", [])
    categories, by_category, missing = {}, {}, []
    for raw in services:
        service = _validate(raw)
        categories.setdefault(service["category"], []).append(service)
        cost = service.get("monthly_brl")
        if cost is None:
            missing.append(service["name"])
        else:
            by_category[service["category"]] = by_category.get(service["category"], 0) + cost
    return {
        "categories": categories,
        "costs": {"by_category": by_category, "total_brl": sum(by_category.values()), "missing": missing},
    }


GROUPS = ("personal", "iot")


def devices(text, hostnames, traffic=None):
    """Catalog devices with online state and, when traffic {hostname: (down, up) Mbps} is given, their rates."""
    seen = [h for h in dict.fromkeys(hostnames) if h and h != "*"]
    result, matched = {g: [] for g in GROUPS}, set()
    totals = {g: [0.0, 0.0] for g in GROUPS}
    for raw in tomllib.loads(text).get("device", []):
        if raw.get("group") not in GROUPS:
            raise CatalogError(f"{raw.get('name')}: unknown group {raw.get('group')!r}")
        hits = [h for h in seen if any(h.lower().startswith(m.lower()) for m in raw.get("match", []))]
        matched.update(hits)
        rates = [traffic[h] for h in hits if traffic and traffic.get(h) and None not in traffic[h]]
        down = round(sum(r[0] for r in rates), 2) if rates else None
        up = round(sum(r[1] for r in rates), 2) if rates else None
        if rates:
            totals[raw["group"]][0] += down
            totals[raw["group"]][1] += up
        result[raw["group"]].append({"name": raw["name"], "online": bool(hits), "down_mbps": down, "up_mbps": up,
                                     **({"icon": raw["icon"]} if "icon" in raw else {})})
    result["unknown"] = [h for h in seen if h not in matched]
    result["traffic"] = {g: {"down_mbps": round(d, 2), "up_mbps": round(u, 2)} for g, (d, u) in totals.items()}
    return result


def _validate(raw):
    name = raw.get("name")
    if not name:
        raise CatalogError("service without name")
    if raw.get("category") not in CATEGORIES:
        raise CatalogError(f"{name}: unknown category {raw.get('category')!r}")
    service = {"role": "active", **raw}
    if service["role"] not in ROLES:
        raise CatalogError(f"{name}: unknown role {service['role']!r}")
    return service
