import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import vrm  # noqa: E402

NOW = 1793536200


def reply(soc=(1793536147, 56), pv=(1793536147, 654), load=(1793536147, 776)):
    # Samme form som målt mot VRM 01.11.2026: data per attributt-id, koder i meta.
    data = {}
    meta = {}
    for attr_id, code, point in (("144", "bs", soc), ("113", "Pdc", pv), ("131", "a1", load)):
        meta[attr_id] = {"code": code}
        if point is not None:
            data[attr_id] = [[point[0] - 60, 50], list(point)]
    return {"success": True, "records": {"data": data, "meta": meta, "instance": 0}}


def lovable(stale=True):
    return {"soc": 55, "pv_w": 0, "load_w": 354, "age_s": 240, "stale": stale}


class ParseTests(unittest.TestCase):
    def test_reads_latest_points(self):
        out = vrm.parse(reply(), NOW)
        self.assertEqual(out["soc"], 56)
        self.assertEqual(out["pv_w"], 654)
        self.assertEqual(out["load_w"], 776)
        self.assertEqual(out["age_s"], 53)
        self.assertTrue(out["online"])

    def test_old_points_mean_offline(self):
        out = vrm.parse(reply(), NOW + 3600)
        self.assertFalse(out["online"])

    def test_missing_soc_means_offline(self):
        out = vrm.parse(reply(soc=None), NOW)
        self.assertIsNone(out["soc"])
        self.assertFalse(out["online"])

    def test_rejects_impossible_soc(self):
        out = vrm.parse(reply(soc=(NOW, 140)), NOW)
        self.assertIsNone(out["soc"])
        self.assertFalse(out["online"])

    def test_empty_reply_is_offline(self):
        out = vrm.parse({"success": True, "records": {}}, NOW)
        self.assertFalse(out["online"])
        self.assertIsNone(out["age_s"])


class MergeTests(unittest.TestCase):
    def test_overrides_values_and_freshness(self):
        data = lovable()
        self.assertTrue(vrm.merge(data, vrm.parse(reply(), NOW)))
        self.assertEqual(data["soc"], 56)
        self.assertEqual(data["pv_w"], 654)
        self.assertEqual(data["load_w"], 776)
        self.assertEqual(data["age_s"], 53)
        self.assertFalse(data["stale"])

    def test_offline_touches_nothing(self):
        data = lovable()
        self.assertFalse(vrm.merge(data, vrm.parse(reply(), NOW + 3600)))
        self.assertEqual(data["soc"], 55)
        self.assertTrue(data["stale"])


if __name__ == "__main__":
    unittest.main()
