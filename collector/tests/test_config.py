import unittest

from homeboard.adguard import adguard
from homeboard.config import ConfigError, parse

MINIMAL = """
[site]
name = "Demo Home"
domain = "example.org"
"""


class ConfigTest(unittest.TestCase):
    def test_defaults_fill_what_the_file_omits(self):
        cfg = parse(MINIMAL)
        self.assertEqual(cfg["site"]["language"], "pt-BR")
        self.assertEqual(cfg["collector"]["interval_seconds"], 60)
        self.assertEqual(cfg["sources"], {})
        self.assertEqual(cfg["probe"], [])

    def test_site_name_is_required(self):
        with self.assertRaisesRegex(ConfigError, "site.name"):
            parse("[site]\ndomain = 'x'\n")

    def test_probe_needs_host_and_url(self):
        with self.assertRaisesRegex(ConfigError, "probe"):
            parse(MINIMAL + '[[probe]]\nhost = "vault"\n')

    def test_secrets_are_not_allowed_in_the_file(self):
        with self.assertRaisesRegex(ConfigError, "password.*environment"):
            parse(MINIMAL + '[sources.adguard]\nurl = "http://dns"\npassword = "hunter2"\n')


class AdguardTest(unittest.TestCase):
    def test_blocked_share_of_queries(self):
        self.assertEqual(adguard({"num_dns_queries": 40000, "num_blocked_filtering": 7200, "avg_processing_time": 0.0123}),
                         {"queries": 40000, "blocked": 7200, "blocked_pct": 18.0, "avg_ms": 12.3})

    def test_no_queries_means_no_share(self):
        self.assertIsNone(adguard({"num_dns_queries": 0, "num_blocked_filtering": 0})["blocked_pct"])


if __name__ == "__main__":
    unittest.main()
