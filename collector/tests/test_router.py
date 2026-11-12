import copy
import unittest

from homeboard.router import router

UPLINKS = [{"dev": "pppoe-wan", "name": "fiber", "probe": "fiber_ok"}, {"dev": "rmnet_mhi0", "name": "5g", "probe": "five_g_ok"}]

STATUS = {
    "time": 1794500000,
    "fiber_ok": True,
    "five_g_ok": True,
    "routes": [{"dev": "pppoe-wan", "metric": 1}, {"dev": "rmnet_mhi0", "metric": 2}],
    "wan_uptime": 274932,
    "counters": {"pppoe-wan": [1_000_000, 500_000], "rmnet_mhi0": [10, 10]},
    "modem": {"rsrp": -76, "sinr": 11, "network_type": "LTE"},
    "wg_handshakes": [1794255090, 0, 0, 1794500000 - 60],
    "leases": ["laptop-ana", "*"],
    "assoc": {"ra0": 4, "rax0": 5, "apcli0": 0},
    "clients": [
        {"name": "laptop-ana", "ip": "192.168.1.20", "iface": "5G", "online": True, "total_rx": "1000000", "total_tx": "500000"},
        {"name": "server", "ip": "192.168.1.10", "iface": "cable", "online": True, "total_rx": "0", "total_tx": "0"},
        {"name": "old-phone", "ip": "192.168.1.30", "iface": "2.4G", "online": False, "total_rx": "5", "total_tx": "5"},
    ],
}


def later(seconds, rx_delta, tx_delta):
    s = copy.deepcopy(STATUS)
    s["time"] += seconds
    s["counters"]["pppoe-wan"] = [STATUS["counters"]["pppoe-wan"][0] + rx_delta, STATUS["counters"]["pppoe-wan"][1] + tx_delta]
    return s


class RouterTest(unittest.TestCase):
    def test_active_uplink_is_the_lowest_metric_route_that_answers(self):
        self.assertEqual(router(STATUS, UPLINKS)["active"], "fiber")
        down = dict(STATUS, fiber_ok=False)
        self.assertEqual(router(down, UPLINKS)["active"], "5g")
        self.assertIsNone(router(dict(down, five_g_ok=False), UPLINKS)["active"])

    def test_rate_comes_from_counter_delta_on_the_active_uplink(self):
        r = router(later(10, 125_000_000, 12_500_000), UPLINKS, previous=STATUS)
        self.assertEqual(r["rate_mbps"], {"down": 100.0, "up": 10.0})

    def test_no_rate_without_previous_sample_or_after_counter_reset(self):
        self.assertIsNone(router(STATUS, UPLINKS)["rate_mbps"])
        self.assertIsNone(router(later(10, -1, -1), UPLINKS, previous=STATUS)["rate_mbps"])

    def test_vpn_peers_active_when_handshake_is_recent(self):
        vpn = router(STATUS, UPLINKS)["vpn"]
        self.assertEqual(vpn, {"peers": 4, "active": 1, "last_handshake": 1794499940})

    def test_wifi_clients_sum_access_point_radios_only(self):
        self.assertEqual(router(STATUS, UPLINKS)["wifi_clients"], 9)

    def test_modem_signal_passes_through(self):
        self.assertEqual(router(STATUS, UPLINKS)["modem"], {"rsrp": -76, "sinr": 11, "type": "LTE"})


if __name__ == "__main__":
    unittest.main()


class ClientsTest(unittest.TestCase):
    def test_client_rates_come_from_counter_deltas(self):
        after = copy.deepcopy(STATUS)
        after["time"] += 10
        after["clients"][0]["total_rx"] = str(1_000_000 + 12_500_000)
        after["clients"][0]["total_tx"] = str(500_000 + 1_250_000)
        laptop = router(after, UPLINKS, previous=STATUS)["clients"][0]
        self.assertEqual(laptop, {"name": "laptop-ana", "ip": "192.168.1.20", "iface": "5G", "online": True,
                                  "down_mbps": 10.0, "up_mbps": 1.0})

    def test_first_sample_has_no_rate_and_offline_clients_are_dropped(self):
        clients = router(STATUS, UPLINKS)["clients"]
        self.assertEqual([c["name"] for c in clients], ["laptop-ana", "server"])
        self.assertIsNone(clients[0]["down_mbps"])

    def test_counter_reset_gives_no_rate(self):
        after = copy.deepcopy(STATUS)
        after["time"] += 10
        after["clients"][0]["total_rx"] = "10"
        self.assertIsNone(router(after, UPLINKS, previous=STATUS)["clients"][0]["down_mbps"])
