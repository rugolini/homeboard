import datetime as dt
import unittest

from homeboard.litellm import spend

DAILY = [  # (day, model_group, usd) as the SQL returns them
    (dt.date(2026, 11, 1), "coordenacao", 0.20),
    (dt.date(2026, 11, 1), "claude-sonnet", 1.00),
    (dt.date(2026, 11, 2), "raciocinio", 0.40),
    (dt.date(2026, 11, 2), "tasks", 0.0),
]
BY_KEY = [("hermes-agent", 1.55), (None, 0.05)]
TIERS = {"raciocinio": "reasoning", "coordenacao": "coordination", "tasks": "tasks"}


class SpendTest(unittest.TestCase):
    def test_month_total(self):
        self.assertEqual(spend(DAILY, BY_KEY, TIERS)["month_usd"], 1.6)

    def test_groups_aliases_into_tiers(self):
        self.assertEqual(spend(DAILY, BY_KEY, TIERS)["by_tier"],
                         {"reasoning": 0.4, "coordination": 0.2, "tasks": 0.0, "other": 1.0})

    def test_daily_series_by_tier(self):
        days = spend(DAILY, BY_KEY, TIERS)["daily"]
        self.assertEqual(days[0], {"day": "2026-11-01", "coordination": 0.2, "other": 1.0})
        self.assertEqual(days[1]["reasoning"], 0.4)

    def test_spend_by_key_names_unnamed_keys(self):
        self.assertEqual(spend(DAILY, BY_KEY, TIERS)["by_key"], [["hermes-agent", 1.55], ["unnamed", 0.05]])


if __name__ == "__main__":
    unittest.main()


class NoTiersTest(unittest.TestCase):
    def test_without_tier_map_everything_is_other(self):
        self.assertEqual(spend(DAILY, [])["by_tier"], {"other": 1.6})
