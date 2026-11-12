"""Edges: each function reaches one real system and hands raw data to a tested parser."""
import base64
import datetime as dt
import json
import os
import pathlib
import shutil
import ssl
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

from . import adguard as adguard_parser
from . import agent as agent_parser
from . import statuspage as statuspage_parser
from . import costs as costs_parser
from . import build, hermes as hermes_parser, litellm as litellm_parser, router as router_parser, unraid as unraid_parser


def _read(path):
    return pathlib.Path(path).read_text()


def _get_json(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _hwmon_temp(root, name):
    for hw in pathlib.Path(root).glob("hwmon*"):
        if (hw / "name").exists() and (hw / "name").read_text().strip() == name:
            return round(int((hw / "temp1_input").read_text()) / 1000)
    return None


def unraid(cfg, state):
    proc = cfg.get("proc", "/host/proc")
    stat = _read(f"{proc}/stat")
    previous, state["proc_stat"] = state.get("proc_stat"), stat
    emhttp = cfg.get("emhttp", "/host/emhttp")
    hwmon = cfg.get("hwmon", "/host/hwmon")
    return {
        "disks": unraid_parser.disks(_read(f"{emhttp}/disks.ini")),
        "array": unraid_parser.array(_read(f"{emhttp}/var.ini")),
        "cpu_pct": unraid_parser.cpu_percent(previous, stat) if previous else None,
        "cpu_temp_c": _hwmon_temp(hwmon, cfg.get("cpu_sensor", "coretemp")),
        "memory": unraid_parser.memory(_read(f"{proc}/meminfo")),
        "uptime_s": int(float(_read(f"{proc}/uptime").split()[0])),
    }


def containers(cfg):
    return _get_json(f"{cfg.get('url', 'http://docker-proxy:2375')}/containers/json?all=1")


def backup(cfg, now):
    return build.backup(_read(cfg["status_file"]), now)


def glinet(cfg, state):
    cmd = ["ssh", "-i", cfg["key"], "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
           "-o", f"UserKnownHostsFile={cfg.get('known_hosts', '/keys/known_hosts')}", cfg["ssh"]]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True).stdout
    status = json.loads(out)
    previous, state["glinet"] = state.get("glinet"), status
    return router_parser.router(status, cfg.get("uplinks", []), previous=previous)


def litellm(cfg, now):
    import pg8000.native  # only needed when this source is configured

    dsn = os.environ[cfg.get("dsn_env", "LITELLM_DSN")]
    user, rest = dsn.split("://", 1)[1].split("@", 1)
    user, password = user.split(":", 1)
    host, db = rest.split("/", 1)
    host, port = (host.split(":") + ["5432"])[:2]
    conn = pg8000.native.Connection(user, password=password, host=host, port=int(port), database=db, timeout=10)
    try:
        month = dict(start=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        daily = conn.run('select date("startTime"), model_group, sum(spend) from "LiteLLM_SpendLogs" '
                         'where "startTime" >= :start group by 1, 2 order by 1', **month)
        keys = conn.run('select t.key_alias, sum(s.spend) from "LiteLLM_SpendLogs" s left join "LiteLLM_VerificationToken" t '
                        'on t.token = s.api_key where s."startTime" >= :start group by 1 order by 2 desc', **month)
        agent = None
        if cfg.get("agent_key"):
            key = dict(key=cfg["agent_key"])
            budget = conn.run('select max_budget, budget_duration, budget_reset_at, spend from "LiteLLM_VerificationToken" '
                              'where key_alias = :key', **key)
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            reqs = conn.run('select s."startTime", s.spend from "LiteLLM_SpendLogs" s join "LiteLLM_VerificationToken" t '
                            'on t.token = s.api_key where t.key_alias = :key and s."startTime" >= :start',
                            start=today - dt.timedelta(days=7), **key)
            b = budget[0] if budget else None
            agent = {
                "budget": b and {"max_usd": float(b[0]) if b[0] is not None else None, "duration": b[1],
                                 "reset_at": b[2].isoformat() if b[2] else None, "spend_usd": float(b[3] or 0)},
                "requests": [(r[0].timestamp(), float(r[1] or 0)) for r in reqs],
            }
    finally:
        conn.close()
    data = litellm_parser.spend([(d, g, float(u or 0)) for d, g, u in daily], [(k, float(u or 0)) for k, u in keys],
                                cfg.get("tiers"))
    data["agent"] = agent
    return data


def hermes(cfg, now):
    src = pathlib.Path(cfg["state_db"])
    with tempfile.TemporaryDirectory() as tmp:
        # Copy db + WAL so a read never touches the live file the agent is writing.
        for suffix in ("", "-wal", "-shm"):
            if (src.parent / (src.name + suffix)).exists():
                shutil.copy2(src.parent / (src.name + suffix), pathlib.Path(tmp) / (src.name + suffix))
        conn = sqlite3.connect(pathlib.Path(tmp) / src.name)
        try:
            data = hermes_parser.summary(conn, now)
            data["activity"] = agent_parser.activity(conn, now)
        finally:
            conn.close()
    if cfg.get("tiers_file") and pathlib.Path(cfg["tiers_file"]).exists():
        data["tiers"] = {t: v.get("model") for t, v in json.loads(_read(cfg["tiers_file"])).items()}
    return data


def adguard(cfg):
    user = os.environ.get(cfg.get("user_env", "ADGUARD_USER"), "")
    password = os.environ.get(cfg.get("password_env", "ADGUARD_PASSWORD"), "")
    headers = {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()} if user else {}
    return adguard_parser.adguard(_get_json(f"{cfg['url']}/control/stats", headers))


PTAX_URL = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarPeriodo("
            "dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)?@dataInicial='{start}'&@dataFinalCotacao='{end}'"
            "&$format=json&$select=cotacaoCompra,cotacaoVenda,dataHoraCotacao")


def fx(state, now):
    """USD/BRL from Banco Central's PTAX, fetched once per day; a week-wide window covers weekends and holidays."""
    cached = state.get("fx")
    if cached and cached["fetched"] == now.date().isoformat():
        return cached["rate"]
    start = (now - dt.timedelta(days=7)).strftime("%m-%d-%Y")
    rate = costs_parser.ptax(_get_json(PTAX_URL.format(start=start, end=now.strftime("%m-%d-%Y")), timeout=15))
    if rate:
        state["fx"] = {"fetched": now.date().isoformat(), "rate": rate}
    return rate or (cached or {}).get("rate")


def statuspages(pages):
    out = {}
    for page in pages:
        try:
            out[page["name"]] = statuspage_parser.statuspage(_get_json(page["url"], timeout=8))
        except (OSError, ValueError) as exc:
            out[page["name"]] = {"up": None, "degraded": False, "description": f"{type(exc).__name__}"}
    return out


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)
# For services with a self-signed certificate on the LAN; set insecure = true on that probe only.
_insecure = ssl.create_default_context()
_insecure.check_hostname = False
_insecure.verify_mode = ssl.CERT_NONE
_opener_insecure = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=_insecure))


def probe(url, insecure=False, timeout=6):
    """Up means the service answered: a login redirect or 401 still proves it is alive."""
    start = time.monotonic()
    try:
        status = (_opener_insecure if insecure else _opener).open(url, timeout=timeout).status
    except urllib.error.HTTPError as err:
        status = err.code
    except (urllib.error.URLError, OSError):
        return {"ok": False, "ms": None}
    return {"ok": status < 500, "ms": round((time.monotonic() - start) * 1000)}


def now_local(tz_name):
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo(tz_name))
    except Exception:
        return dt.datetime.now().astimezone()
