import unittest

from homeboard.agent import task_label
from homeboard.dockerstats import container_stats


class TaskLabelTest(unittest.TestCase):
    def test_goal_from_the_request(self):
        self.assertEqual(task_label("analise esse video https://youtu.be/x", []), "video")
        self.assertEqual(task_label("faça a revisão semanal do Hermes", []), "weekly_review")
        self.assertEqual(task_label("Refaça a gravação no Obsidian da análise", []), "note")
        self.assertEqual(task_label("quanto está o backup?", []), "backup")

    def test_falls_back_to_what_the_tools_are_doing(self):
        self.assertEqual(task_label("hmm", ["web_search_plus", "web_search_plus", "terminal"]), "web_search")
        self.assertEqual(task_label(None, ["browser_navigate"]), "browsing")
        self.assertEqual(task_label("", ["terminal"]), "server")
        self.assertEqual(task_label("", ["write_file"]), "editing")

    def test_unknown_is_generic_work(self):
        self.assertEqual(task_label("oi", []), "working")


STATS = {
    "cpu_stats": {"cpu_usage": {"total_usage": 2_000_000_000}, "system_cpu_usage": 20_000_000_000, "online_cpus": 8},
    "precpu_stats": {"cpu_usage": {"total_usage": 1_000_000_000}, "system_cpu_usage": 10_000_000_000},
    "memory_stats": {"usage": 800_000_000, "limit": 8_000_000_000, "stats": {"inactive_file": 100_000_000}},
    "networks": {"eth0": {"rx_bytes": 10, "tx_bytes": 20}, "eth1": {"rx_bytes": 1, "tx_bytes": 2}},
    "pids_stats": {"current": 42},
}


class ContainerStatsTest(unittest.TestCase):
    def test_cpu_memory_network_and_processes(self):
        self.assertEqual(container_stats(STATS), {"cpu_pct": 80.0, "mem_bytes": 700_000_000, "mem_limit_bytes": 8_000_000_000,
                                                  "net_rx_bytes": 11, "net_tx_bytes": 22, "pids": 42})

    def test_missing_previous_sample_gives_no_cpu(self):
        stats = {**STATS, "precpu_stats": {"cpu_usage": {}}}
        self.assertIsNone(container_stats(stats)["cpu_pct"])


if __name__ == "__main__":
    unittest.main()
