"""Tests that do not require a display or libmpv."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tv_app.channel_store import ChannelStore
from tv_app.hdhomerun import HdhrError, _parse_lineup, normalize_device_url
from tv_app.settings import AppSettings


class NormalizeTests(unittest.TestCase):
    def test_accepts_host_and_lineup_urls(self) -> None:
        self.assertEqual(normalize_device_url("192.168.1.27"), "http://192.168.1.27")
        self.assertEqual(normalize_device_url("http://192.168.1.27/"), "http://192.168.1.27")
        self.assertEqual(
            normalize_device_url("http://192.168.1.27/lineup.json"),
            "http://192.168.1.27",
        )
        self.assertEqual(
            normalize_device_url("https://hdhomerun.local/discover.json"),
            "https://hdhomerun.local",
        )

    def test_rejects_blank(self) -> None:
        with self.assertRaises(HdhrError):
            normalize_device_url("")


class LineupTests(unittest.TestCase):
    def test_skips_entries_without_url(self) -> None:
        channels = _parse_lineup(
            [
                {
                    "GuideNumber": "2.1",
                    "GuideName": "NBC",
                    "URL": "http://192.168.1.27:5004/auto/v2.1",
                    "Tags": "favorite",
                },
                {
                    "GuideNumber": "4.1",
                    "GuideName": "FOX",
                    "URL": "http://192.168.1.27:5004/auto/v4.1",
                    "Tags": "drm",
                },
                {"GuideNumber": "x", "GuideName": "bad", "URL": ""},
            ]
        )
        self.assertEqual([c.display_name for c in channels], ["2.1  NBC", "4.1  FOX  (DRM)"])
        self.assertTrue(channels[1].has_drm)


class StoreTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "channels.json"
            store = ChannelStore(path)
            for existing in list(store.list()):
                store.remove(existing.id)
            added = store.add("NBC", "http://192.168.1.27:5004/auto/v2.1")
            reloaded = ChannelStore(path)
            found = reloaded.get(added.id)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.name, "NBC")
            neighbor = reloaded.neighbor(added.id, 1)
            self.assertIsNotNone(neighbor)
            assert neighbor is not None
            self.assertEqual(neighbor.id, added.id)
            self.assertTrue(reloaded.remove(added.id))
            self.assertEqual(reloaded.list(), [])


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            AppSettings(osc_enabled=False).save(path)
            self.assertFalse(AppSettings.load(path).osc_enabled)


if __name__ == "__main__":
    unittest.main()
