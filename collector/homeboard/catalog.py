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


def devices(text, hostnames):
    """Catalog devices with online state, from the hostnames the router leased."""
    seen = [h for h in dict.fromkeys(hostnames) if h and h != "*"]
    result, matched = {g: [] for g in GROUPS}, set()
    for raw in tomllib.loads(text).get("device", []):
        if raw.get("group") not in GROUPS:
            raise CatalogError(f"{raw.get('name')}: unknown group {raw.get('group')!r}")
        hits = [h for h in seen if any(h.lower().startswith(m.lower()) for m in raw.get("match", []))]
        matched.update(hits)
        result[raw["group"]].append({"name": raw["name"], "online": bool(hits), **({"icon": raw["icon"]} if "icon" in raw else {})})
    result["unknown"] = [h for h in seen if h not in matched]
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
