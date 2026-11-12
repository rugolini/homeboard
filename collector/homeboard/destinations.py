"""Traffic per catalog service: router per-destination byte deltas matched against each service's IP prefixes."""
import ipaddress


def by_service(ct, prefixes):
    seconds = (ct or {}).get("seconds") or 0
    if seconds <= 0:
        return {}
    nets = sorted(((name, ipaddress.ip_network(p, strict=False)) for name, ps in prefixes.items() for p in ps),
                  key=lambda n: -n[1].prefixlen)
    totals = {}
    for ip, (up, down) in ct.get("dst", {}).items():
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        name = next((n for n, net in nets if addr.version == net.version and addr in net), "_other")
        t = totals.setdefault(name, [0, 0])
        t[0] += up
        t[1] += down
    return {n: {"up_mbps": round(u * 8 / seconds / 1e6, 2), "down_mbps": round(d * 8 / seconds / 1e6, 2)}
            for n, (u, d) in totals.items()}
