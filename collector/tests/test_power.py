import unittest

from homeboard.power import stations

DELTA = {"name": "Delta 2", "capacity_wh": 1024,
         "level": "sensor.d2_battery_level", "input_w": "sensor.d2_input_power",
         "output_w": "sensor.d2_output_power", "grid_w": "sensor.d2_ac_input_power",
         "reserve_pct": "number.d2_discharge_limit"}


def states(**values):
    names = {"level": "sensor.d2_battery_level", "input_w": "sensor.d2_input_power", "output_w": "sensor.d2_output_power",
             "grid_w": "sensor.d2_ac_input_power", "reserve_pct": "number.d2_discharge_limit"}
    return [{"entity_id": names[k], "state": str(v)} for k, v in values.items()]


class StationsTest(unittest.TestCase):
    def test_on_grid_passthrough(self):
        [s] = stations(states(level="100.0", input_w=90, output_w=90, grid_w=90, reserve_pct=10), [DELTA])
        self.assertEqual(s, {"name": "Delta 2", "level_pct": 100.0, "input_w": 90.0, "output_w": 90.0,
                             "on_grid": True, "charging": False, "runtime_min": 614})

    def test_on_battery_runtime_shrinks_with_load(self):
        [s] = stations(states(level=50, input_w=0, output_w=200, grid_w=0, reserve_pct=10), [DELTA])
        self.assertEqual((s["on_grid"], s["charging"], s["runtime_min"]), (False, False, 123))

    def test_unavailable_entities_become_none(self):
        [s] = stations(states(level="unavailable", output_w=0), [DELTA])
        self.assertEqual((s["level_pct"], s["input_w"], s["on_grid"], s["runtime_min"]), (None, None, None, None))


if __name__ == "__main__":
    unittest.main()
