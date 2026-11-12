import unittest

from homeboard.costs import breakdown, ptax

PTAX = {"value": [
    {"cotacaoCompra": 5.5140, "cotacaoVenda": 5.5146, "dataHoraCotacao": "2026-11-09 13:11:19.041465"},
    {"cotacaoCompra": 5.5834, "cotacaoVenda": 5.5840, "dataHoraCotacao": "2026-11-10 13:06:01.353639"},
]}

CATALOG = {
    "categories": {
        "connection": [{"name": "Fiber", "monthly_brl": 100.0}, {"name": "5G", "monthly_brl": 478.72}],
        "cloud": [{"name": "Drive", "monthly_brl": 96.99}],
        "dns": [{"name": "Free DNS", "monthly_brl": 0}],
        "ai": [{"name": "Assistant"}],
    },
    "costs": {"by_category": {"connection": 578.72, "cloud": 96.99, "dns": 0}, "total_brl": 675.71, "missing": ["Assistant"]},
}
AI = {"month_usd": 10.0, "by_tier": {"reasoning": 2.0, "other": 8.0}}
FX = {"usd_brl": 5.5, "date": "2026-11-10"}


class PtaxTest(unittest.TestCase):
    def test_uses_the_latest_selling_rate(self):
        self.assertEqual(ptax(PTAX), {"usd_brl": 5.584, "date": "2026-11-10"})

    def test_empty_response_has_no_rate(self):
        self.assertIsNone(ptax({"value": []}))


class BreakdownTest(unittest.TestCase):
    def test_total_is_subscriptions_plus_ai_converted(self):
        b = breakdown(CATALOG, AI, FX)
        self.assertEqual(b["total_brl"], 675.71 + 55.0)

    def test_parts_add_up_to_the_total(self):
        b = breakdown(CATALOG, AI, FX)
        self.assertAlmostEqual(sum(p["brl"] for p in b["parts"]), b["total_brl"])

    def test_subscriptions_are_split_by_category_with_paid_items_only(self):
        sub = breakdown(CATALOG, AI, FX)["parts"][0]
        self.assertEqual(sub["key"], "subscriptions")
        self.assertEqual([(c["key"], c["brl"]) for c in sub["children"]], [("connection", 578.72), ("cloud", 96.99)])
        self.assertEqual([i["name"] for i in sub["children"][0]["items"]], ["Fiber", "5G"])

    def test_ai_usage_is_converted_per_tier_and_keeps_dollars(self):
        ai = breakdown(CATALOG, AI, FX)["parts"][1]
        self.assertEqual(ai["key"], "ai_usage")
        self.assertEqual(ai["usd"], 10.0)
        self.assertEqual([(c["key"], c["brl"], c["usd"]) for c in ai["children"]], [("reasoning", 11.0, 2.0), ("other", 44.0, 8.0)])

    def test_without_exchange_rate_ai_stays_out_of_the_total(self):
        b = breakdown(CATALOG, AI, None)
        self.assertEqual(b["total_brl"], 675.71)
        self.assertIsNone(b["parts"][1]["brl"])

    def test_missing_items_are_listed(self):
        self.assertEqual(breakdown(CATALOG, AI, FX)["missing"], ["Assistant"])


if __name__ == "__main__":
    unittest.main()
