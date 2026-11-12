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
        self.assertEqual([(d["name"], d["online"]) for d in result["personal"]], [("Laptop", True), ("Phone", False)])
        self.assertEqual([(d["name"], d["online"]) for d in result["iot"]], [("TV", False), ("Air conditioner", True)])

    def test_match_is_a_case_insensitive_prefix(self):
        self.assertTrue(devices(CATALOG, ["PHONE-ana"])["personal"][1]["online"])

    def test_lists_unmatched_hostnames_once_and_ignores_placeholders(self):
        result = devices(CATALOG, ["mixer-1a2b3c", "*", "", "mixer-1a2b3c"])
        self.assertEqual(result["unknown"], ["mixer-1a2b3c"])

    def test_traffic_is_summed_per_device_and_per_group(self):
        traffic = {"laptop-ana": (3.0, 0.5), "ac-livingroom": (0.1, 0.02), "mixer-1a2b3c": (1.0, 1.0)}
        result = devices(CATALOG, list(traffic), traffic)
        self.assertEqual(result["personal"][0]["down_mbps"], 3.0)
        self.assertEqual(result["traffic"]["personal"], {"down_mbps": 3.0, "up_mbps": 0.5})
        self.assertEqual(result["traffic"]["iot"], {"down_mbps": 0.1, "up_mbps": 0.02})

    def test_devices_without_traffic_data_have_no_rate(self):
        self.assertIsNone(devices(CATALOG, ["laptop-ana"])["personal"][0]["down_mbps"])

    def test_rejects_unknown_group(self):
        with self.assertRaisesRegex(CatalogError, "X.*group"):
            devices('[[device]]\nname = "X"\ngroup = "guests"\nmatch = ["x"]\n', [])


if __name__ == "__main__":
    unittest.main()
