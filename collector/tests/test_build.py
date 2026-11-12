import datetime as dt
import json
import unittest

from homeboard.build import apps, backup, build

NOW = dt.datetime(2026, 11, 12, 15, 0, tzinfo=dt.timezone.utc)


class BuildTest(unittest.TestCase):
    def test_each_source_becomes_a_block(self):
        status = build({"a": lambda: {"x": 1}}, NOW)
        self.assertEqual(status["blocks"]["a"], {"ok": True, "data": {"x": 1}})
        self.assertEqual(status["generated_at"], NOW.isoformat())

    def test_failing_source_is_marked_unavailable_without_breaking_others(self):
        def boom():
            raise OSError("ssh: connect timed out")
        status = build({"bad": boom, "good": lambda: 2}, NOW)
        self.assertEqual(status["blocks"]["bad"], {"ok": False, "error": "OSError: ssh: connect timed out"})
        self.assertEqual(status["blocks"]["good"]["data"], 2)

    def test_output_is_json_serializable(self):
        json.dumps(build({"a": lambda: {"t": 1.5, "l": [1]}}, NOW))


CATALOG = """
[[app]]
label = "Passwords"
container = "vaultwarden"
host = "vaultwarden"

[[app]]
label = "Music"
container = "RoonServer"

[[app]]
label = "Home"
host = "homeassistant"
"""


class AppsTest(unittest.TestCase):
    def test_app_is_up_when_container_runs_and_http_answers(self):
        containers = [{"Names": ["/vaultwarden"], "State": "running"}, {"Names": ["/RoonServer"], "State": "exited"}]
        probes = {"vaultwarden": {"ok": True, "ms": 12}, "homeassistant": {"ok": False, "ms": None}}
        result = apps(CATALOG, containers, probes)
        self.assertEqual(result[0], {"label": "Passwords", "host": "vaultwarden", "state": "up", "ms": 12})
        self.assertEqual(result[1]["state"], "paused")
        self.assertEqual(result[2]["state"], "down")

    def test_missing_container_is_down(self):
        self.assertEqual(apps(CATALOG, [], {"vaultwarden": {"ok": True, "ms": 5}})[0]["state"], "down")


class BackupTest(unittest.TestCase):
    def test_recent_successful_backup(self):
        text = json.dumps({"time": NOW.timestamp() - 3600 * 10, "ok": True, "seconds": 360})
        self.assertEqual(backup(text, NOW), {"ok": True, "age_hours": 10.0, "seconds": 360, "stale": False, "error": None})

    def test_backup_older_than_26_hours_is_stale(self):
        text = json.dumps({"time": NOW.timestamp() - 3600 * 30, "ok": True, "seconds": 300})
        self.assertTrue(backup(text, NOW)["stale"])

    def test_failed_backup_keeps_the_error(self):
        text = json.dumps({"time": NOW.timestamp(), "ok": False, "error": "rsync failed for: domains"})
        self.assertEqual(backup(text, NOW)["error"], "rsync failed for: domains")


if __name__ == "__main__":
    unittest.main()
