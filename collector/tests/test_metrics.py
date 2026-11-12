import unittest

from homeboard.metrics import metrics

STATUS = {
    "blocks": {
        "server": {"ok": True, "data": {
            "cpu_pct": 12.5, "cpu_temp_c": 41, "memory": {"used_bytes": 100, "total_bytes": 400},
            "disks": [{"name": "disk1", "temp_c": 38, "spinning": True, "healthy": True, "used_bytes": 10, "size_bytes": 20},
                      {"name": "parity", "temp_c": None, "spinning": False, "healthy": True, "used_bytes": None, "size_bytes": None}]}},
        "router": {"ok": True, "data": {"active": "fibra", "uplinks": {"fibra": True, "5G": True},
                                        "rate_mbps": {"down": 80.5, "up": 9.0}, "wifi_clients": 9,
                                        "modem": {"rsrp": -77, "sinr": 11}, "vpn": {"active": 1, "peers": 4}}},
        "probes": {"ok": True, "data": {"vault": {"ok": True, "ms": 12}, "nas": {"ok": False, "ms": None}}},
        "ai_spend": {"ok": True, "data": {"month_usd": 22.1, "by_tier": {"tarefas": 0.0, "other": 1.5}}},
        "backup": {"ok": True, "data": {"ok": True, "age_hours": 2.5, "stale": False}},
        "dns": {"ok": False, "error": "boom"},
    },
    "catalog": {"costs": {"total_brl": 698.64}},
    "devices": {"personal": [{"name": "Laptop", "online": True, "down_mbps": 2.5, "up_mbps": 0.5}, {"name": "Phone", "online": False}], "iot": [],
                "unknown": ["x"], "traffic": {"personal": {"down_mbps": 2.5, "up_mbps": 0.5}, "iot": {"down_mbps": 0, "up_mbps": 0}}},
}


class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.text = metrics(STATUS)

    def test_gauges_carry_labels(self):
        self.assertIn('homeboard_disk_temperature_celsius{disk="disk1"} 38', self.text)
        self.assertIn('homeboard_disk_spinning{disk="parity"} 0', self.text)
        self.assertIn('homeboard_probe_up{host="nas"} 0', self.text)
        self.assertIn('homeboard_uplink_up{uplink="5G"} 1', self.text)
        self.assertIn('homeboard_uplink_active{uplink="fibra"} 1', self.text)

    def test_missing_values_are_left_out_not_zeroed(self):
        self.assertNotIn('homeboard_disk_temperature_celsius{disk="parity"}', self.text)
        self.assertNotIn('homeboard_probe_latency_seconds{host="nas"}', self.text)

    def test_every_source_reports_whether_it_answered(self):
        self.assertIn('homeboard_source_up{source="server"} 1', self.text)
        self.assertIn('homeboard_source_up{source="dns"} 0', self.text)

    def test_units_follow_prometheus_conventions(self):
        self.assertIn('homeboard_probe_latency_seconds{host="vault"} 0.012', self.text)
        self.assertIn("homeboard_wan_rate_bits_per_second{direction=\"down\"} 80500000", self.text)
        self.assertIn("homeboard_backup_age_seconds 9000", self.text)

    def test_costs_and_devices(self):
        self.assertIn("homeboard_ai_spend_month_usd 22.1", self.text)
        self.assertIn('homeboard_ai_spend_month_usd_by_tier{tier="other"} 1.5', self.text)
        self.assertIn("homeboard_subscriptions_monthly_brl 698.64", self.text)
        self.assertIn('homeboard_devices_online{group="personal"} 1', self.text)

    def test_device_and_group_traffic(self):
        self.assertIn('homeboard_device_traffic_bits_per_second{device="Laptop",direction="down"} 2500000', self.text)
        self.assertIn('homeboard_group_traffic_bits_per_second{group="personal",direction="up"} 500000', self.text)

    def test_each_metric_has_help_and_type_once(self):
        self.assertEqual(self.text.count("# TYPE homeboard_disk_temperature_celsius gauge"), 1)
        self.assertTrue(self.text.endswith("\n"))

    def test_label_values_are_escaped(self):
        odd = {"blocks": {"probes": {"ok": True, "data": {'a"b\\c': {"ok": True, "ms": 1}}}}}
        self.assertIn('homeboard_probe_up{host="a\\"b\\\\c"} 1', metrics(odd))


if __name__ == "__main__":
    unittest.main()
