import calendar
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import netconfig  # noqa: E402
import portal  # noqa: E402

DEVICE = "od3-benk-01"


def live(**overrides):
    data = {
        "now": "2026-11-01T03:19:15.108Z",
        "devices": [
            {
                "device_id": DEVICE,
                "last_report_at": "2026-11-01T03:18:00.201134+00:00",
                "last_next_wake_in_s": 300,
            }
        ],
        "energy": {
            DEVICE: {
                "sources": {
                    "device": {"p_w": 6.5},
                    "victron": {
                        "soc_pct": 55,
                        "batt_v": 53.3,
                        "batt_w": -234,
                        "pv_w": 0,
                        "ovrige": {"ac_load_w": 354, "ac_source": 240, "batt_state": 2},
                    },
                }
            }
        },
        "aggregat": {"dc_a": -7.3, "genbat_v": 12.7, "vebus_error": 0},
        "fukt": {
            DEVICE: {
                "vinkjeller": {"doegntrend": {"til_rh_pct": 75.29}},
                "teknisk": {"doegntrend": {"til_rh_pct": 64.12}},
            }
        },
        "rh_grense_pct": 87,
        "active_operation": {},
    }
    data.update(overrides)
    return data


class TimeTests(unittest.TestCase):
    def test_matches_calendar(self):
        for text, parts in (
            ("2026-11-01T03:18:00.201134+00:00", (2026, 11, 1, 3, 18, 0)),
            ("2028-02-29T23:59:59Z", (2028, 2, 29, 23, 59, 59)),
            ("2027-01-01T00:00:00.000Z", (2027, 1, 1, 0, 0, 0)),
        ):
            self.assertEqual(portal.parse_time(text), calendar.timegm(parts + (0, 0, 0)))

    def test_age_text(self):
        self.assertEqual(portal.age_text(75), "75 s")
        self.assertEqual(portal.age_text(600), "10 min")
        self.assertEqual(portal.age_text(4 * 3600), "4 t")
        self.assertEqual(portal.age_text(72 * 3600), "3 d")


class ParseTests(unittest.TestCase):
    def test_reads_measured_response(self):
        data = portal.parse(live())
        self.assertEqual(data["soc"], 55)
        self.assertEqual(data["load_w"], 354)
        self.assertEqual(data["age_s"], 75)
        self.assertFalse(data["stale"])
        self.assertEqual(data["cellar_rh"], 75.29)
        self.assertEqual(data["start_v"], 12.7)
        self.assertEqual(data["target_pct"], 5)

    def test_bank_uses_multiplus_not_batt_w(self):
        self.assertAlmostEqual(portal.parse(live())["bank_w"], 53.3 * -7.3 - 6.5)

    def test_bank_unknown_without_dc_current(self):
        data = portal.parse(live(aggregat={}))
        self.assertIsNone(data["bank_w"])
        self.assertIsNone(data["hours"])
        self.assertEqual(data["soc"], 55)

    def test_old_report_is_stale(self):
        data = portal.parse(live(now="2026-11-01T03:40:00Z"))
        self.assertTrue(data["stale"])

    def test_report_within_promised_wake_is_fresh(self):
        self.assertFalse(portal.parse(live(now="2026-11-01T03:31:00Z"))["stale"])

    def test_missing_soc_is_none_and_stale(self):
        energy = {DEVICE: {"sources": {"device": {"p_w": 6.5}}}}
        data = portal.parse(live(energy=energy))
        self.assertIsNone(data["soc"])
        self.assertTrue(data["stale"])

    def test_generator_targets_stop_level(self):
        raw = live(aggregat={"dc_a": 28.0, "ac_in_w": 2300})
        source = raw["energy"][DEVICE]["sources"]["victron"]
        source["ovrige"]["ac_source"] = 2
        data = portal.parse(raw)
        self.assertTrue(data["generator_on"])
        self.assertEqual(data["target_pct"], 90)

    def test_operation_gets_norwegian_name(self):
        raw = live(active_operation={DEVICE: {"operation": "dehumidify"}})
        self.assertEqual(portal.parse(raw)["operation"], "Avfukting")

    def test_no_device_is_an_error(self):
        with self.assertRaises(ValueError):
            portal.parse({"now": "2026-11-01T03:19:15Z", "devices": []})

    def test_no_estimate_when_not_heading_there(self):
        self.assertIsNone(portal.hours_to(95, 90, 1500))
        self.assertIsNone(portal.hours_to(55, 5, -10))


class NetconfigTests(unittest.TestCase):
    def test_round_trip_with_norwegian_name(self):
        data = netconfig.encode("Hytta på Åsen", "p@ss w&rd=æ")
        padded = data + bytes(40)
        self.assertEqual(netconfig.decode(padded), ("Hytta på Åsen", "p@ss w&rd=æ"))

    def test_empty_storage_is_none(self):
        self.assertIsNone(netconfig.decode(bytes(100)))
        self.assertIsNone(netconfig.decode(b"\xff" * 100))

    def test_rejects_invalid_lengths(self):
        with self.assertRaises(ValueError):
            netconfig.encode("", "x")
        with self.assertRaises(ValueError):
            netconfig.encode("a" * 33, "x")
        with self.assertRaises(ValueError):
            netconfig.encode("nett", "x" * 64)

    def test_parses_form_from_phone(self):
        body = b"ssid=Hytta+p%C3%A5+%C3%85sen&other=&password=a%2Bb%26c%3Dd"
        self.assertEqual(
            netconfig.parse_form(body),
            {"ssid": "Hytta på Åsen", "other": "", "password": "a+b&c=d"},
        )

    def test_escapes_network_names(self):
        self.assertEqual(netconfig.escape('<a"&>'), "&lt;a&quot;&amp;&gt;")


if __name__ == "__main__":
    unittest.main()
