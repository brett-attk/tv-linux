"""Main application window: channel list + embedded mpv TV pane."""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from .channel_store import Channel, ChannelStore
from .logging_setup import get_logger, log_path
from .player import MpvPlayer
from .settings import AppSettings
from .ui.channel_list import ChannelListPane
from .ui.controls import PlaybackBar
from .ui.dialogs import ChannelDialog, confirm_remove, show_about
from .ui.import_dialog import HdhrImportDialog

log = get_logger(__name__)


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="TV")
        self.set_default_size(1100, 650)
        self.set_border_width(0)

        self.settings = AppSettings.load()
        self.store = ChannelStore()
        self.player = MpvPlayer(osc_enabled=self.settings.osc_enabled)
        self._current: Optional[Channel] = None
        self._ui_fullscreen = False
        self._player_ready = False

        self.player.set_fullscreen_handler(self._on_mpv_fullscreen)
        self._build_ui()
        self._reload_list()
        self.connect("key-press-event", self._on_key_press)
        self.connect("window-state-event", self._on_window_state)
        self.connect("destroy", self._on_destroy)
        # GTK 3: present() alone does not show child widgets.
        self.show_all()

    def _build_ui(self) -> None:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(outer)
        self.menu_bar = self._build_menu_bar()
        outer.pack_start(self.menu_bar, False, False, 0)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer.pack_start(root, True, True, 0)

        self.channels = ChannelListPane(
            on_play=self._on_play_requested,
            on_stop=self._stop_playback,
            on_edit=self._on_edit,
            on_remove=self._on_remove,
            on_toggle_favorite=self._on_toggle_favorite,
        )
        root.pack_start(self.channels, False, False, 0)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        right.set_hexpand(True)
        right.set_vexpand(True)

        # EventBox gives a stable native X11 window for libmpv --wid embedding.
        self.video_area = Gtk.EventBox()
        self.video_area.set_visible_window(True)
        self.video_area.set_hexpand(True)
        self.video_area.set_vexpand(True)
        self.video_area.set_halign(Gtk.Align.FILL)
        self.video_area.set_valign(Gtk.Align.FILL)
        self.video_area.set_size_request(640, 360)
        self.video_area.override_background_color(
            Gtk.StateFlags.NORMAL, Gdk.RGBA(0.05, 0.05, 0.05, 1.0)
        )
        self.video_area.set_double_buffered(False)
        self.video_area.connect("realize", self._on_video_realize)
        right.pack_start(self.video_area, True, True, 0)

        self.controls = PlaybackBar(
            on_prev=lambda: self._change_channel(-1),
            on_next=lambda: self._change_channel(1),
            on_volume_down=self._on_vol_down,
            on_volume_up=self._on_vol_up,
            on_mute=self._on_mute_toggled,
            on_osc=self._on_osc_toggled,
            on_fullscreen=self._on_fullscreen_clicked,
            osc_enabled=self.settings.osc_enabled,
        )
        right.pack_start(self.controls, False, False, 0)
        root.pack_start(right, True, True, 0)

    def _build_menu_bar(self) -> Gtk.MenuBar:
        menu_bar = Gtk.MenuBar()

        settings_menu = Gtk.Menu()
        settings_root = Gtk.MenuItem(label="Settings")
        settings_root.set_submenu(settings_menu)

        add_item = Gtk.MenuItem(label="Add Channel…")
        add_item.connect("activate", lambda *_: self._on_add())
        settings_menu.append(add_item)

        import_item = Gtk.MenuItem(label="Import from HDHomeRun…")
        import_item.connect("activate", lambda *_: self._on_import())
        settings_menu.append(import_item)

        settings_menu.append(Gtk.SeparatorMenuItem())

        about_item = Gtk.MenuItem(label="About")
        about_item.connect("activate", lambda *_: self._on_about())
        settings_menu.append(about_item)

        menu_bar.append(settings_root)
        return menu_bar

    def _on_video_realize(self, widget: Gtk.EventBox) -> None:
        window = widget.get_window()
        if window is None:
            log.error("Video area realized without a GDK window")
            return
        try:
            wid = window.get_xid()
        except Exception:
            log.exception("Failed to read X11 window id for video embedding")
            GLib.idle_add(
                self._show_error,
                "Video embedding requires X11 (run via ./run.sh).",
            )
            return
        if not wid:
            log.error("X11 window id was empty for video pane")
            GLib.idle_add(self._show_error, "Could not get X11 window id for video pane.")
            return
        try:
            self.player.attach(wid)
        except Exception as exc:
            log.exception("Failed to attach mpv to wid=%s", wid)
            GLib.idle_add(
                self._show_error,
                f"Failed to embed mpv: {exc}\nDetails: {log_path()}",
            )
            return
        self._player_ready = True
        log.info("mpv attached to wid=%s", wid)
        channels = self.store.list()
        if channels:
            self.channels.select(channels[0].id)

    def _show_error(self, message: str) -> bool:
        log.error("Showing error dialog: %s", message)
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()
        return False

    def _reload_list(self, select_id: Optional[str] = None) -> None:
        playing_id = self._current.id if self._current else None
        self.channels.reload(
            self.store.list(),
            select_id=select_id or playing_id,
            playing_id=playing_id,
        )

    def _selected_channel(self) -> Optional[Channel]:
        channel_id = self.channels.selected_id()
        if channel_id is None:
            return None
        return self.store.get(channel_id)

    def _on_play_requested(self, channel_id: str) -> None:
        channel = self.store.get(channel_id)
        if channel is not None:
            self._play_channel(channel)

    def _snapshot_window_size(self) -> tuple[int, int]:
        return self.get_size()

    def _restore_window_size(self, size: tuple[int, int]) -> bool:
        """Undo any geometry nudge from mpv/GTK size requests during play/stop."""
        width, height = size
        if width > 1 and height > 1 and self.get_size() != (width, height):
            self.resize(width, height)
        return False

    def _schedule_size_restore(self, size: tuple[int, int], *, delayed: bool) -> None:
        GLib.idle_add(self._restore_window_size, size)
        GLib.timeout_add(100, self._restore_window_size, size)
        if delayed:
            GLib.timeout_add(500, self._restore_window_size, size)

    def _play_channel(self, channel: Channel) -> None:
        size = self._snapshot_window_size()
        self._current = channel
        self.controls.set_now_playing(channel.name)
        if self._player_ready:
            self.player.play(channel.url)
        self.channels.select(channel.id)
        self.channels.set_playing(channel.id)
        self._schedule_size_restore(size, delayed=True)

    def _stop_playback(self) -> None:
        size = self._snapshot_window_size()
        self._current = None
        self.controls.set_now_playing(None)
        self.channels.set_playing(None)
        if self._player_ready:
            self.player.stop()
        self._schedule_size_restore(size, delayed=False)

    def _change_channel(self, delta: int) -> None:
        channels = self.store.list()
        if not channels:
            return
        current_id = self._current.id if self._current else None
        if current_id is None:
            selected = self._selected_channel()
            current_id = selected.id if selected else channels[0].id
        neighbor = self.store.neighbor(current_id, delta)
        if neighbor is not None:
            self._play_channel(neighbor)

    def _on_about(self) -> None:
        show_about(self)

    def _on_add(self) -> None:
        dialog = ChannelDialog(self, "Add Channel")
        while True:
            response = dialog.run()
            if response != Gtk.ResponseType.OK:
                break
            values = dialog.get_values()
            if values is None:
                continue
            name, url = values
            channel = self.store.add(name, url)
            self._reload_list(select_id=channel.id)
            self._play_channel(channel)
            break
        dialog.destroy()

    def _on_import(self) -> None:
        dialog = HdhrImportDialog(self, existing_urls=[c.url for c in self.store.list()])
        response = dialog.run()
        selected = dialog.get_selected_channels() if response == Gtk.ResponseType.OK else []
        dialog.destroy()
        if not selected:
            return
        last_id = None
        try:
            for channel in selected:
                last_id = self.store.add(channel.display_name, channel.url).id
        except OSError as exc:
            log.exception("Failed while importing %s channel(s)", len(selected))
            self._show_error(f"Could not save imported channels: {exc}\nDetails: {log_path()}")
            self._reload_list(select_id=last_id)
            return
        log.info("Imported %s HDHomeRun channel(s)", len(selected))
        self._reload_list(select_id=last_id)

    def _on_edit(self) -> None:
        channel = self._selected_channel()
        if channel is None:
            return
        dialog = ChannelDialog(self, "Edit Channel", channel=channel)
        while True:
            response = dialog.run()
            if response != Gtk.ResponseType.OK:
                break
            values = dialog.get_values()
            if values is None:
                continue
            name, url = values
            # Capture before update(); ChannelStore mutates the same object.
            old_url = channel.url
            updated = self.store.update(channel.id, name, url)
            if updated is not None:
                self._reload_list(select_id=updated.id)
                if self._current and self._current.id == updated.id:
                    if updated.url != old_url:
                        # URL change: reload on the mpv worker thread.
                        self._play_channel(updated)
                    else:
                        # Name-only edit: refresh UI without interrupting playback.
                        self._current = updated
                        self.controls.set_now_playing(updated.name)
                        self.channels.set_playing(updated.id)
            break
        dialog.destroy()

    def _on_toggle_favorite(self) -> None:
        channel = self._selected_channel()
        if channel is None:
            return
        updated = self.store.set_favorite(channel.id, not channel.favorite)
        if updated is not None:
            self._reload_list(select_id=updated.id)

    def _on_remove(self) -> None:
        channel = self._selected_channel()
        if channel is None or not confirm_remove(self, channel.name):
            return
        was_playing = self._current is not None and self._current.id == channel.id
        index = self.store.index_of(channel.id)
        self.store.remove(channel.id)
        if was_playing:
            self._stop_playback()
        remaining = self.store.list()
        select_id = None
        if remaining and index >= 0:
            # Prefer the channel that takes this slot; otherwise the previous one.
            select_id = remaining[min(index, len(remaining) - 1)].id
        self._reload_list(select_id=select_id)

    def _on_vol_up(self) -> None:
        self.controls.set_volume(self.player.volume_up(), self.player.muted)

    def _on_vol_down(self) -> None:
        self.controls.set_volume(self.player.volume_down(), self.player.muted)

    def _on_mute_toggled(self, muted: bool) -> None:
        self.player.set_mute(muted)
        self.controls.set_volume(self.player.volume, self.player.muted)

    def _on_mute_key(self) -> None:
        muted = self.player.mute_toggle()
        self.controls.set_muted(muted)
        self.controls.set_volume(self.player.volume, muted)

    def _on_osc_toggled(self, enabled: bool) -> None:
        self.player.set_osc_enabled(enabled)
        self.settings.osc_enabled = enabled
        try:
            self.settings.save()
        except OSError as exc:
            log.exception("Failed to persist OSC setting")
            self._show_error(f"Could not save settings: {exc}\nDetails: {log_path()}")

    def _on_fullscreen_clicked(self) -> None:
        self._set_ui_fullscreen(not self._ui_fullscreen)

    def _set_chrome_visible(self, visible: bool) -> None:
        for widget in (self.menu_bar, self.channels, self.controls):
            widget.set_visible(visible)

    def _set_ui_fullscreen(self, enabled: bool) -> None:
        self._ui_fullscreen = enabled
        if enabled:
            self._set_chrome_visible(False)
            self.fullscreen()
        else:
            self.unfullscreen()
            self._set_chrome_visible(True)
        if self._player_ready:
            self.player.set_fullscreen(enabled)

    def _on_mpv_fullscreen(self, enabled: bool) -> None:
        GLib.idle_add(self._apply_mpv_fullscreen, enabled)

    def _apply_mpv_fullscreen(self, enabled: bool) -> bool:
        if enabled != self._ui_fullscreen:
            self._set_ui_fullscreen(enabled)
        return False

    def _on_window_state(self, _widget, event) -> bool:
        if event.changed_mask & Gdk.WindowState.FULLSCREEN:
            is_fs = bool(event.new_window_state & Gdk.WindowState.FULLSCREEN)
            if not is_fs and self._ui_fullscreen:
                self._ui_fullscreen = False
                self._set_chrome_visible(True)
                if self._player_ready:
                    self.player.set_fullscreen(False)
        return False

    def _on_key_press(self, _widget, event) -> bool:
        key = event.keyval
        if key == Gdk.KEY_Escape and self._ui_fullscreen:
            self._set_ui_fullscreen(False)
            return True
        if key in (Gdk.KEY_f, Gdk.KEY_F) and not (event.state & Gdk.ModifierType.CONTROL_MASK):
            focus = self.get_focus()
            if isinstance(focus, Gtk.Entry):
                return False
            self._set_ui_fullscreen(not self._ui_fullscreen)
            return True
        if key in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self._on_vol_up()
            return True
        if key in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            self._on_vol_down()
            return True
        if key in (Gdk.KEY_m, Gdk.KEY_M):
            self._on_mute_key()
            return True
        if key == Gdk.KEY_Page_Up:
            self._change_channel(-1)
            return True
        if key == Gdk.KEY_Page_Down:
            self._change_channel(1)
            return True
        return False

    def _on_destroy(self, *_args) -> None:
        self.player.shutdown()
