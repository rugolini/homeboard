import unittest

from homeboard.destinations import by_service

PREFIXES = {"Anthropic": ["160.79.104.0/23"], "GitHub": ["140.82.112.0/20", "2a0a:a440::/29"]}
CT = {"seconds": 10, "dst": {
    "160.79.104.10": [1_250_000, 2_500_000],
    "140.82.113.21": [0, 1_250_000],
    "2a0a:a440::1": [0, 1_250_000],
    "8.8.8.8": [125_000, 125_000],
}}


class ByServiceTest(unittest.TestCase):
    def test_bytes_are_summed_per_service_as_mbps(self):
        out = by_service(CT, PREFIXES)
        self.assertEqual(out["Anthropic"], {"up_mbps": 1.0, "down_mbps": 2.0})
        self.assertEqual(out["GitHub"], {"up_mbps": 0.0, "down_mbps": 2.0})

    def test_unknown_destinations_go_to_other(self):
        self.assertEqual(by_service(CT, PREFIXES)["_other"], {"up_mbps": 0.1, "down_mbps": 0.1})

    def test_no_interval_means_no_rates(self):
        self.assertEqual(by_service({"seconds": 0, "dst": CT["dst"]}, PREFIXES), {})

    def test_most_specific_prefix_wins(self):
        prefixes = {"Cloudflare": ["198.41.128.0/17"], "Tunnel": ["198.41.192.0/20"]}
        out = by_service({"seconds": 10, "dst": {"198.41.192.57": [1_250_000, 0]}}, prefixes)
        self.assertEqual(list(out), ["Tunnel"])

    def test_bad_addresses_are_ignored(self):
        self.assertIn("Anthropic", by_service({"seconds": 10, "dst": {"not-an-ip": [1, 1], **CT["dst"]}}, PREFIXES))


if __name__ == "__main__":
    unittest.main()
