# homeboard

A single, friendly control panel for a self-hosted home: how the house reaches the internet, what runs on the
server, which services you pay for, and what your automation agent is doing — on one live map.

- **Live network map**: internet, uplinks (active in color, standby in grey), router, personal and IoT device groups,
  the server with its apps, and cloud services grouped by category. Hover anything for details.
- **Server health**: disks (spinning or asleep), temperatures, parity, space, last backup.
- **Availability history**: 30-day uptime and downtime per app and per uplink, sampled every minute.
- **Costs**: every subscription grouped by category, plus month-to-date AI spend from LiteLLM.
- **Agent**: what a [Hermes](https://github.com/NousResearch/hermes-agent) agent did today and its latest steps,
  with secrets redacted.

The UI is static HTML that reads `status.json`; a small Python collector writes that file. No database, no build step.
The same server exposes `/metrics` in Prometheus format, so Prometheus can keep long history and Grafana can chart it.

## Quick start (demo data)

```sh
PYTHONPATH=collector HOMEBOARD_CONFIG=examples/demo/homeboard.toml python3 -m homeboard.main
# open http://127.0.0.1:8080
```

The demo reads the fictional files in `examples/demo/`.

## How it works

```
sources (read-only) ──► collector (Python, every 60 s) ──► data/status.json ──► web/ (HTML + JS)
                               └─ data/history.json (30 days of availability)
```

Each source is optional: configure it and its section appears; leave it out and the section is hidden. A configured
source that fails shows as *unavailable* without affecting the others.

| Source | Reads | Config |
|---|---|---|
| Unraid | `/var/local/emhttp/*.ini`, `/proc`, hwmon (never wakes a disk) | `[sources.unraid]` |
| Docker | container states, through a socket proxy that only allows listing | `[sources.docker]` |
| Backup | a JSON status file your backup job writes (`time`, `ok`, `seconds`, `error`) | `[sources.backup]` |
| GL.iNet router | uplinks, failover, rates, 5G signal, WireGuard, DHCP, Wi-Fi via [`adapters/gl-inet`](adapters/gl-inet/homeboard-status.sh) | `[sources.glinet]` |
| LiteLLM | month-to-date spend per tier and per key (read-only Postgres user) | `[sources.litellm]` |
| Hermes agent | a copy of `state.db` (never the live file) | `[sources.hermes]` |
| AdGuard Home | queries and block rate | `[sources.adguard]` |
| Exchange rate | USD/BRL from Banco Central's PTAX, once a day, to show AI spend in reais | `[sources.fx]` |
| Status pages | Atlassian Statuspage `/api/v2/status.json` (Claude, Cloudflare, GitHub…); link a service with `status = "page:<name>"` | `[[statuspage]]` |
| HTTP probes | any URL; a login redirect or 401 still counts as up (`insecure = true` for a self-signed LAN certificate) | `[[probe]]` |

The catalog lives in the same file: `[[service]]` (name, category, `active`/`standby`, monthly cost, Fluent icon,
optional live `status` such as `uplink:fiber` or `app:<host>`, and `asn`/`ip_ranges` to measure live traffic to it), `[[device]]` (matched by DHCP hostname prefix) and
`[[app]]` (label, container, host). See [`examples/demo/homeboard.toml`](examples/demo/homeboard.toml).

## Security

- **homeboard has no login of its own.** Put it behind an authenticating proxy (Cloudflare Access, Authelia, a VPN).
- Secrets never go in the config file; the loader refuses keys like `password` or `token`. Pass them as environment
  variables (`LITELLM_DSN`, `ADGUARD_USER`, `ADGUARD_PASSWORD`).
- Host paths are mounted read-only, the container runs as an unprivileged user with a read-only root filesystem.
- The router key should be a dedicated key restricted to the status script with `command=` in `authorized_keys`.
- Agent steps are truncated and pass through a redaction filter for API keys and tokens before reaching the page.

## Development

```sh
python3 -m unittest discover -s collector/tests -t collector
```

Parsers are pure functions tested with real-shaped fixtures; the code that touches real systems lives in
`collector/homeboard/sources.py` and `main.py`.

## Credits

Icons: [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) by Microsoft (MIT). Fonts: Plus Jakarta Sans and
JetBrains Mono (SIL Open Font License), served by Google Fonts.

## License

[MIT](LICENSE)
