"""Tests that do not require a display or libmpv."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tv_app.channel_store import ChannelStore
from tv_app.hdhomerun import HdhrError, _parse_lineup, normalize_device_url
from tv_app.logging_setup import setup_logging
from tv_app.settings import AppSettings


def setUpModule() -> None:
    # Keep test logs out of the user's real state directory.
    setup_logging(Path(tempfile.mkdtemp()) / "error.log")


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

    def test_scan_in_progress(self) -> None:
        with self.assertRaises(HdhrError) as ctx:
            _parse_lineup({"ScanInProgress": 1, "Channels": []})
        self.assertIn("scanning", str(ctx.exception).lower())


class StoreTests(unittest.TestCase):
    def test_first_start_creates_empty_channels_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tv-app" / "channels.json"
            self.assertFalse(path.exists())
            store = ChannelStore(path)
            self.assertTrue(path.exists())
            self.assertEqual(store.list(), [])
            self.assertEqual(
                path.read_text(encoding="utf-8").strip(),
                '{\n  "channels": []\n}',
            )

    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "channels.json"
            store = ChannelStore(path)
            self.assertEqual(store.list(), [])
            added = store.add("NBC", "http://192.168.1.27:5004/auto/v2.1")
            reloaded = ChannelStore(path)
            found = reloaded.get(added.id)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.name, "NBC")
            self.assertFalse(found.favorite)
            neighbor = reloaded.neighbor(added.id, 1)
            self.assertIsNotNone(neighbor)
            assert neighbor is not None
            self.assertEqual(neighbor.id, added.id)
            self.assertTrue(reloaded.remove(added.id))
            self.assertEqual(reloaded.list(), [])

    def test_favorite_persists_and_sorts_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "channels.json"
            store = ChannelStore(path)
            a = store.add("A", "http://example/a")
            b = store.add("B", "http://example/b")
            c = store.add("C", "http://example/c")
            self.assertEqual([ch.name for ch in store.list()], ["A", "B", "C"])

            updated = store.set_favorite(b.id, True)
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertTrue(updated.favorite)
            self.assertEqual([ch.name for ch in store.list()], ["B", "A", "C"])

            # Neighbor follows display order (favorites first).
            for current_id, expected_id in (
                (b.id, a.id),
                (a.id, c.id),
                (c.id, b.id),
            ):
                neighbor = store.neighbor(current_id, 1)
                self.assertIsNotNone(neighbor)
                assert neighbor is not None
                self.assertEqual(neighbor.id, expected_id)

            reloaded = ChannelStore(path)
            found = reloaded.get(b.id)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertTrue(found.favorite)
            self.assertEqual([ch.name for ch in reloaded.list()], ["B", "A", "C"])

            store.set_favorite(b.id, False)
            self.assertEqual([ch.name for ch in store.list()], ["A", "B", "C"])


class SettingsTests(unittest.TestCase):
    def test_first_start_creates_default_settings_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tv-app" / "settings.json"
            self.assertFalse(path.exists())
            settings = AppSettings.load(path)
            self.assertTrue(path.exists())
            self.assertTrue(settings.osc_enabled)

    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            AppSettings(osc_enabled=False).save(path)
            self.assertFalse(AppSettings.load(path).osc_enabled)


if __name__ == "__main__":
    unittest.main()
