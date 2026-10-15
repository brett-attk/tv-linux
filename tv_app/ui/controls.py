"""Bottom transport bar: channel, volume, OSC, and fullscreen."""

from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango

Action = Callable[[], None]
ToggleAction = Callable[[bool], None]


class PlaybackBar(Gtk.Box):
    def __init__(
        self,
        *,
        on_prev: Action,
        on_next: Action,
        on_volume_down: Action,
        on_volume_up: Action,
        on_mute: ToggleAction,
        on_osc: ToggleAction,
        on_fullscreen: Action,
        osc_enabled: bool,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._on_mute = on_mute
        self.set_margin_top(6)
        self.set_margin_bottom(8)
        self.set_margin_start(8)
        self.set_margin_end(8)

        self.prev_btn = Gtk.Button(label="◀ Prev")
        self.next_btn = Gtk.Button(label="Next ▶")
        self.vol_down_btn = Gtk.Button(label="Vol −")
        self.vol_up_btn = Gtk.Button(label="Vol +")
        self.mute_btn = Gtk.ToggleButton(label="Mute")
        self.osc_btn = Gtk.ToggleButton(label="OSC")
        self.osc_btn.set_tooltip_text("Show on-screen controls on the video")
        self.osc_btn.set_active(osc_enabled)
        self.fs_btn = Gtk.Button(label="Fullscreen")
        self.fs_btn.set_size_request(120, -1)

        self.prev_btn.connect("clicked", lambda *_: on_prev())
        self.next_btn.connect("clicked", lambda *_: on_next())
        self.vol_down_btn.connect("clicked", lambda *_: on_volume_down())
        self.vol_up_btn.connect("clicked", lambda *_: on_volume_up())
        self.mute_btn.connect("toggled", self._mute_toggled)
        self.osc_btn.connect("toggled", lambda button: on_osc(bool(button.get_active())))
        self.fs_btn.connect("clicked", lambda *_: on_fullscreen())

        for button in (
            self.prev_btn,
            self.next_btn,
            self.vol_down_btn,
            self.vol_up_btn,
            self.mute_btn,
            self.osc_btn,
            self.fs_btn,
        ):
            self.pack_start(button, False, False, 0)

        self.now_playing = Gtk.Label(label="Now Playing: —", xalign=0)
        self.now_playing.set_ellipsize(Pango.EllipsizeMode.END)
        self.now_playing.set_hexpand(True)
        self.now_playing.set_width_chars(16)
        self.now_playing.set_max_width_chars(16)
        self.pack_end(self.now_playing, True, True, 0)

        self.volume_label = Gtk.Label(xalign=1.0)
        self.volume_label.set_width_chars(10)
        self.volume_label.set_max_width_chars(10)
        self.volume_label.set_text("Vol  80")
        self.pack_end(self.volume_label, False, False, 0)

    def set_now_playing(self, name: Optional[str]) -> None:
        self.now_playing.set_text("Now Playing: —" if not name else f"Now Playing: {name}")

    def set_volume(self, volume: int, muted: bool) -> None:
        mark = "M" if muted else " "
        self.volume_label.set_text(f"Vol {volume:3d}{mark}")

    def set_muted(self, muted: bool) -> None:
        """Sync the mute toggle without re-entering its handler."""
        self.mute_btn.handler_block_by_func(self._mute_toggled)
        self.mute_btn.set_active(muted)
        self.mute_btn.handler_unblock_by_func(self._mute_toggled)

    def _mute_toggled(self, button: Gtk.ToggleButton) -> None:
        self._on_mute(bool(button.get_active()))
