import unittest

from homeboard.unraid import array, cpu_percent, disks, memory

DISKS_INI = '''["parity"]
name="parity"
type="Parity"
rotational="1"
spundown="1"
temp="*"
status="DISK_OK"
numErrors="0"
color="green-blink"
["disk1"]
name="disk1"
type="Data"
rotational="1"
spundown="0"
temp="39"
status="DISK_OK"
numErrors="0"
color="green-on"
fsSize="7811939620"
fsUsed="1637582640"
["cache"]
name="cache"
type="Cache"
rotational="0"
spundown="0"
temp="30"
status="DISK_OK"
numErrors="0"
color="green-on"
fsSize="483655684"
fsUsed="119432408"
["flash"]
name="flash"
type="Flash"
status="DISK_OK"
'''

VAR_INI = '''mdState="STARTED"
sbSynced="1794191038"
sbSyncErrs="0"
mdResync="0"
mdNumDisabled="0"
mdNumInvalid="0"
'''


class DisksTest(unittest.TestCase):
    def test_lists_array_and_pool_disks_without_the_flash(self):
        self.assertEqual([d["name"] for d in disks(DISKS_INI)], ["parity", "disk1", "cache"])

    def test_spun_down_disk_has_no_temperature(self):
        parity = disks(DISKS_INI)[0]
        self.assertEqual((parity["spinning"], parity["temp_c"]), (False, None))

    def test_reads_temperature_usage_and_health(self):
        disk1 = disks(DISKS_INI)[1]
        self.assertEqual(disk1["temp_c"], 39)
        self.assertEqual(disk1["used_bytes"], 1637582640 * 1024)
        self.assertEqual(disk1["size_bytes"], 7811939620 * 1024)
        self.assertTrue(disk1["healthy"])

    def test_disk_with_errors_or_red_color_is_unhealthy(self):
        bad = DISKS_INI.replace('numErrors="0"\ncolor="green-on"\nfsSize="7811939620"', 'numErrors="3"\ncolor="green-on"\nfsSize="7811939620"')
        self.assertFalse(disks(bad)[1]["healthy"])
        red = DISKS_INI.replace('color="green-blink"', 'color="red-on"')
        self.assertFalse(disks(red)[0]["healthy"])


class ArrayTest(unittest.TestCase):
    def test_started_array_with_valid_parity(self):
        self.assertEqual(array(VAR_INI), {"started": True, "parity_errors": 0, "last_check": 1794191038,
                                          "checking": False, "disabled": 0})

    def test_resync_in_progress(self):
        self.assertTrue(array(VAR_INI.replace('mdResync="0"', 'mdResync="15625879500"'))["checking"])


class SystemTest(unittest.TestCase):
    def test_cpu_percent_from_two_proc_stat_samples(self):
        before = "cpu  100 0 100 800 0 0 0 0 0 0\n"
        after = "cpu  130 0 120 850 0 0 0 0 0 0\n"
        self.assertEqual(cpu_percent(before, after), 50.0)

    def test_memory_used_excludes_available(self):
        meminfo = "MemTotal:       65536000 kB\nMemFree:  1000 kB\nMemAvailable:   40960000 kB\n"
        self.assertEqual(memory(meminfo), {"total_bytes": 65536000 * 1024, "used_bytes": (65536000 - 40960000) * 1024})


if __name__ == "__main__":
    unittest.main()
