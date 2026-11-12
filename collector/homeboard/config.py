"""The single TOML file that describes one home. Secrets never live in it: they come from the environment."""
import re
import tomllib

_SECRET_KEY = re.compile(r"(password|token|secret|api_key|dsn)$")


class ConfigError(ValueError):
    pass


def parse(text):
    raw = tomllib.loads(text)
    site = raw.get("site", {})
    if not site.get("name"):
        raise ConfigError("site.name is required")
    for name, source in raw.get("sources", {}).items():
        for key in source:
            if _SECRET_KEY.search(key):
                raise ConfigError(f"sources.{name}.{key}: put the password/token in the environment and name it with {key}_env")
    for probe in raw.get("probe", []):
        if not probe.get("host") or not probe.get("url"):
            raise ConfigError(f"probe needs host and url: {probe}")
    return {
        "site": {"language": "pt-BR", "domain": None, **site},
        "collector": {"interval_seconds": 60, "data_dir": "/data", "web_dir": "/app/web", "port": 8080, **raw.get("collector", {})},
        "sources": raw.get("sources", {}),
        "probe": raw.get("probe", []),
        "map": raw.get("map", {}),
        "raw_text": text,
    }
