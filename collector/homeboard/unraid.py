"""Parsers for Unraid's emhttp state files (/var/local/emhttp) and the host's /proc."""
import re

_SECTION = re.compile(r'^\["?([^"\]]+)"?\]$')
_PAIR = re.compile(r'^([^=]+)="(.*)"$')


def parse_ini(text):
    current = {}
    sections = {None: current}
    for line in text.splitlines():
        line = line.strip()
        if m := _SECTION.match(line):
            current = sections.setdefault(m.group(1), {})
        elif m := _PAIR.match(line):
            current[m.group(1)] = m.group(2)
    return sections


def _int(value):
    return int(value) if value and value.lstrip("-").isdigit() else None


def disks(text):
    out = []
    for name, d in parse_ini(text).items():
        if name is None or d.get("type") == "Flash":
            continue
        size, used = _int(d.get("fsSize")), _int(d.get("fsUsed"))
        out.append({
            "name": name,
            "type": d.get("type", "").lower(),
            "rotational": d.get("rotational") == "1",
            "spinning": d.get("spundown") != "1",
            "temp_c": _int(d.get("temp")),
            # emhttp reports filesystem sizes in KiB.
            "size_bytes": size * 1024 if size is not None else None,
            "used_bytes": used * 1024 if used is not None else None,
            "healthy": d.get("status") == "DISK_OK" and _int(d.get("numErrors")) == 0
                       and d.get("color", "green").startswith("green"),
        })
    return out


def array(text):
    v = parse_ini(text)[None]
    return {
        "started": v.get("mdState") == "STARTED",
        "parity_errors": _int(v.get("sbSyncErrs")),
        "last_check": _int(v.get("sbSynced")),
        "checking": (_int(v.get("mdResync")) or 0) > 0,
        "disabled": (_int(v.get("mdNumDisabled")) or 0) + (_int(v.get("mdNumInvalid")) or 0),
    }


def _cpu_times(proc_stat):
    fields = [int(x) for x in proc_stat.splitlines()[0].split()[1:]]
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    return sum(fields), idle


def cpu_percent(before, after):
    total0, idle0 = _cpu_times(before)
    total1, idle1 = _cpu_times(after)
    busy = (total1 - total0) - (idle1 - idle0)
    return round(100 * busy / (total1 - total0), 1) if total1 > total0 else 0.0


def memory(meminfo):
    kb = {k: int(v.split()[0]) for k, v in (line.split(":", 1) for line in meminfo.splitlines() if ":" in line)}
    return {"total_bytes": kb["MemTotal"] * 1024, "used_bytes": (kb["MemTotal"] - kb["MemAvailable"]) * 1024}
