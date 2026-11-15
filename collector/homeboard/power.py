"""Battery stations (portable power stations, UPS) read from Home Assistant entity states."""


def _value(by_id, entity):
    try:
        return float(by_id[entity]) if entity else None
    except (KeyError, ValueError):
        return None


def stations(states, configured):
    by_id = {s["entity_id"]: s["state"] for s in states}
    out = []
    for cfg in configured:
        level, inp, outp, grid, reserve = (_value(by_id, cfg.get(k)) for k in
                                           ("level", "input_w", "output_w", "grid_w", "reserve_pct"))
        usable_wh = (level - (reserve or 0)) / 100 * cfg["capacity_wh"] if level is not None and cfg.get("capacity_wh") else None
        out.append({
            "name": cfg["name"],
            "level_pct": level,
            "input_w": inp,
            "output_w": outp,
            "on_grid": grid > 0 if grid is not None else None,
            "charging": inp > outp if inp is not None and outp is not None else None,
            "runtime_min": round(max(usable_wh, 0) / outp * 60) if usable_wh is not None and outp else None,
        })
    return out
