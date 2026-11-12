import unittest

from homeboard.catalog import CatalogError, load

VALID = """
[[service]]
name = "Fiber ISP"
category = "connection"
role = "active"
monthly_brl = 150

[[service]]
name = "Mobile 5G"
category = "connection"
role = "standby"
monthly_brl = 240

[[service]]
name = "Netflix"
category = "streaming"
monthly_brl = 45
"""


class LoadTest(unittest.TestCase):
    def test_groups_services_by_category_in_file_order(self):
        catalog = load(VALID)
        self.assertEqual([s["name"] for s in catalog["categories"]["connection"]], ["Fiber ISP", "Mobile 5G"])
        self.assertEqual([s["name"] for s in catalog["categories"]["streaming"]], ["Netflix"])

    def test_role_defaults_to_active(self):
        netflix = load(VALID)["categories"]["streaming"][0]
        self.assertEqual(netflix["role"], "active")

    def test_monthly_totals_per_category_and_overall(self):
        costs = load(VALID)["costs"]
        self.assertEqual(costs["by_category"], {"connection": 390, "streaming": 45})
        self.assertEqual(costs["total_brl"], 435)

    def test_unknown_cost_is_reported_not_counted(self):
        catalog = load(VALID + '\n[[service]]\nname = "Google One"\ncategory = "cloud"\n')
        self.assertEqual(catalog["costs"]["missing"], ["Google One"])
        self.assertEqual(catalog["costs"]["total_brl"], 435)

    def test_rejects_unknown_category(self):
        with self.assertRaisesRegex(CatalogError, "Foo.*category"):
            load('[[service]]\nname = "Foo"\ncategory = "games"\n')

    def test_rejects_unknown_role(self):
        with self.assertRaisesRegex(CatalogError, "Foo.*role"):
            load('[[service]]\nname = "Foo"\ncategory = "ai"\nrole = "maybe"\n')

    def test_rejects_service_without_name(self):
        with self.assertRaisesRegex(CatalogError, "name"):
            load('[[service]]\ncategory = "ai"\n')


if __name__ == "__main__":
    unittest.main()
