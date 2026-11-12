import unittest

from homeboard.catalog import CatalogError, devices

CATALOG = """
[[device]]
name = "Laptop"
group = "personal"
match = ["laptop-ana"]

[[device]]
name = "Phone"
group = "personal"
match = ["phone"]

[[device]]
name = "TV"
group = "iot"
match = ["tv-"]

[[device]]
name = "Air conditioner"
group = "iot"
match = ["ac-"]
"""


class DevicesTest(unittest.TestCase):
    def test_marks_catalog_devices_online_when_a_hostname_matches(self):
        result = devices(CATALOG, ["laptop-ana", "ac-livingroom"])
        self.assertEqual(result["personal"], [{"name": "Laptop", "online": True}, {"name": "Phone", "online": False}])
        self.assertEqual(result["iot"], [{"name": "TV", "online": False}, {"name": "Air conditioner", "online": True}])

    def test_match_is_a_case_insensitive_prefix(self):
        self.assertTrue(devices(CATALOG, ["PHONE-ana"])["personal"][1]["online"])

    def test_lists_unmatched_hostnames_once_and_ignores_placeholders(self):
        result = devices(CATALOG, ["mixer-1a2b3c", "*", "", "mixer-1a2b3c"])
        self.assertEqual(result["unknown"], ["mixer-1a2b3c"])

    def test_rejects_unknown_group(self):
        with self.assertRaisesRegex(CatalogError, "X.*group"):
            devices('[[device]]\nname = "X"\ngroup = "guests"\nmatch = ["x"]\n', [])


if __name__ == "__main__":
    unittest.main()
