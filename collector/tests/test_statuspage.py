import unittest

from homeboard.statuspage import statuspage


class StatuspageTest(unittest.TestCase):
    def test_operational_page_is_up(self):
        page = {"status": {"indicator": "none", "description": "All Systems Operational"}}
        self.assertEqual(statuspage(page), {"up": True, "degraded": False, "description": "All Systems Operational"})

    def test_minor_incident_is_up_but_degraded(self):
        page = {"status": {"indicator": "minor", "description": "Partially Degraded Service"}}
        self.assertEqual(statuspage(page)["degraded"], True)
        self.assertTrue(statuspage(page)["up"])

    def test_major_or_critical_is_down(self):
        for level in ("major", "critical"):
            self.assertFalse(statuspage({"status": {"indicator": level, "description": "x"}})["up"])


if __name__ == "__main__":
    unittest.main()
