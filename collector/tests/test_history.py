import datetime as dt
import unittest

from homeboard.history import History

DAY = dt.date(2026, 11, 12)


def at(day, hour=12):
    return dt.datetime.combine(day, dt.time(hour))


class HistoryTest(unittest.TestCase):
    def test_uptime_is_ok_samples_over_all_samples(self):
        h = History()
        for ok in (True, True, True, False):
            h.record("fiber", ok, at(DAY))
        self.assertEqual(h.uptime("fiber", today=DAY), 75.0)

    def test_unknown_check_has_no_uptime(self):
        self.assertIsNone(History().uptime("nada", today=DAY))

    def test_daily_bars_cover_30_days_oldest_first(self):
        h = History()
        h.record("fiber", True, at(DAY))
        h.record("fiber", False, at(DAY - dt.timedelta(days=1)))
        bars = h.daily("fiber", today=DAY)
        self.assertEqual(len(bars), 30)
        self.assertEqual(bars[-1], 100.0)
        self.assertEqual(bars[-2], 0.0)
        self.assertIsNone(bars[0])

    def test_samples_older_than_30_days_are_dropped(self):
        h = History()
        h.record("fiber", False, at(DAY - dt.timedelta(days=40)))
        h.record("fiber", True, at(DAY))
        self.assertEqual(h.uptime("fiber", today=DAY), 100.0)

    def test_downtime_minutes_assume_one_sample_per_minute(self):
        h = History()
        for ok in (True, False, False):
            h.record("fiber", ok, at(DAY))
        self.assertEqual(h.downtime_minutes("fiber", today=DAY), 2)

    def test_round_trips_through_plain_dict(self):
        h = History()
        h.record("fiber", False, at(DAY))
        self.assertEqual(History.from_dict(h.to_dict()).uptime("fiber", today=DAY), 0.0)


if __name__ == "__main__":
    unittest.main()
