"""Per-check availability kept as daily [ok, total] counters for the last 30 days."""
import datetime as dt

WINDOW_DAYS = 30


class History:
    def __init__(self, days=None):
        self._days = days or {}  # check -> {"YYYY-MM-DD": [ok, total]}

    def record(self, check, ok, when):
        day = self._days.setdefault(check, {}).setdefault(when.date().isoformat(), [0, 0])
        day[0] += 1 if ok else 0
        day[1] += 1
        self._prune(check, when.date())

    def _prune(self, check, today):
        oldest = (today - dt.timedelta(days=WINDOW_DAYS - 1)).isoformat()
        for key in [k for k in self._days[check] if k < oldest]:
            del self._days[check][key]

    def _window(self, check, today):
        oldest = (today - dt.timedelta(days=WINDOW_DAYS - 1)).isoformat()
        return {k: v for k, v in self._days.get(check, {}).items() if k >= oldest}

    def uptime(self, check, today):
        days = self._window(check, today).values()
        total = sum(t for _, t in days)
        return round(100 * sum(o for o, _ in days) / total, 2) if total else None

    def downtime_minutes(self, check, today):
        return sum(t - o for o, t in self._window(check, today).values())

    def daily(self, check, today):
        days = self._window(check, today)
        out = []
        for back in range(WINDOW_DAYS - 1, -1, -1):
            ok_total = days.get((today - dt.timedelta(days=back)).isoformat())
            out.append(round(100 * ok_total[0] / ok_total[1], 1) if ok_total else None)
        return out

    def to_dict(self):
        return self._days

    @classmethod
    def from_dict(cls, data):
        return cls({check: {d: list(v) for d, v in days.items()} for check, days in data.items()})
