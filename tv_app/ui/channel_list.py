"""Channel list pane: click-to-select rows and per-row play/stop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk, Pango

from ..channel_store import Channel

PlayHandler = Callable[[str], None]
StopHandler = Callable[[], None]
ActionHandler = Callable[[], None]

_PLAY_ICON = "media-playback-start-symbolic"
_STOP_ICON = "media-playback-stop-symbolic"
_FAVORITE_ICON = "emblem-favorite-symbolic"
_BTN_SIZE = 28
_HEART_SIZE = 16


@dataclass
class _Row:
    channel_id: str
    favorite: bool
    play_btn: Gtk.Button
    play_image: Gtk.Image


class ChannelListPane(Gtk.Box):
    """Left-hand channel list; Edit / Remove / Favorite via right-click menu."""

    def __init__(
        self,
        on_play: PlayHandler,
        on_stop: StopHandler,
        on_edit: ActionHandler,
        on_remove: ActionHandler,
        on_toggle_favorite: ActionHandler,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._on_play = on_play
        self._on_stop = on_stop
        self._on_edit = on_edit
        self._on_remove = on_remove
        self._on_toggle_favorite = on_toggle_favorite
        self._playing_id: Optional[str] = None
        self._rows: dict[Gtk.ListBoxRow, _Row] = {}

        # Fixed width so row content cannot steal space from the video pane.
        self.set_size_request(280, -1)
        self.set_hexpand(False)
        self.set_hexpand_set(True)
        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_margin_start(8)
        self.set_margin_end(4)

        heading = Gtk.Label(label="Channels", xalign=0)
        heading.get_style_context().add_class("title")
        self.pack_start(heading, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_propagate_natural_width(False)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.connect("row-selected", self._on_row_selected)
        # Capture phase so right-click works even over child widgets (e.g. play).
        gesture = Gtk.GestureMultiPress.new(self.list_box)
        gesture.set_button(Gdk.BUTTON_SECONDARY)
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        gesture.connect("pressed", self._on_secondary_pressed)
        self._context_gesture = gesture
        scrolled.add(self.list_box)
        self.pack_start(scrolled, True, True, 0)

    def reload(
        self,
        channels: Iterable[Channel],
        *,
        select_id: Optional[str] = None,
        playing_id: Optional[str] = None,
    ) -> None:
        self._playing_id = playing_id
        for child in self.list_box.get_children():
            self.list_box.remove(child)
        self._rows.clear()

        selected: Optional[Gtk.ListBoxRow] = None
        for channel in channels:
            row = self._make_row(channel)
            self.list_box.add(row)
            if select_id and channel.id == select_id:
                selected = row
            elif playing_id and channel.id == playing_id and selected is None:
                selected = row

        self.list_box.show_all()
        if selected is not None:
            self.list_box.select_row(selected)
        self._update_play_buttons()

    def set_playing(self, channel_id: Optional[str]) -> None:
        self._playing_id = channel_id
        self._update_play_buttons()

    def select(self, channel_id: str) -> None:
        for row, meta in self._rows.items():
            if meta.channel_id == channel_id:
                self.list_box.select_row(row)
                return

    def selected_id(self) -> Optional[str]:
        row = self.list_box.get_selected_row()
        if row is None:
            return None
        meta = self._rows.get(row)
        return meta.channel_id if meta is not None else None

    def _make_row(self, channel: Channel) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(4)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        if channel.favorite:
            heart = Gtk.Image.new_from_icon_name(_FAVORITE_ICON, Gtk.IconSize.MENU)
            heart.set_pixel_size(_HEART_SIZE)
            heart.set_valign(Gtk.Align.CENTER)
            box.pack_start(heart, False, False, 0)

        label = Gtk.Label(label=channel.name, xalign=0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_hexpand(True)
        box.pack_start(label, True, True, 0)

        # Fixed slot so play/stop icon swaps never reflow the row.
        slot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        slot.set_size_request(_BTN_SIZE, _BTN_SIZE)
        slot.set_valign(Gtk.Align.CENTER)

        play_btn = Gtk.Button()
        play_btn.set_relief(Gtk.ReliefStyle.NONE)
        play_btn.set_can_focus(False)
        play_btn.set_size_request(_BTN_SIZE, _BTN_SIZE)
        image = Gtk.Image.new_from_icon_name(_PLAY_ICON, Gtk.IconSize.BUTTON)
        image.set_pixel_size(16)
        play_btn.set_image(image)
        play_btn.set_always_show_image(True)
        play_btn.set_opacity(0.0)
        play_btn.set_sensitive(False)
        play_btn.connect("clicked", self._on_play_clicked, channel.id)
        slot.pack_start(play_btn, True, True, 0)
        box.pack_end(slot, False, False, 0)

        row.add(box)
        self._rows[row] = _Row(channel.id, channel.favorite, play_btn, image)
        return row

    def _on_secondary_pressed(
        self, _gesture: Gtk.GestureMultiPress, _n_press: int, _x: float, y: float
    ) -> None:
        row = self.list_box.get_row_at_y(int(y))
        if row is None or row not in self._rows:
            return
        self.list_box.select_row(row)
        self._popup_channel_menu()

    def _popup_channel_menu(self) -> None:
        menu = Gtk.Menu()
        row = self.list_box.get_selected_row()
        meta = self._rows.get(row) if row is not None else None
        favorite = meta.favorite if meta is not None else False

        fav_label = "Remove from favorites" if favorite else "Favorite this channel"
        fav_item = Gtk.MenuItem(label=fav_label)
        fav_item.connect("activate", lambda *_: self._on_toggle_favorite())
        menu.append(fav_item)

        edit_item = Gtk.MenuItem(label="Edit")
        edit_item.connect("activate", lambda *_: self._on_edit())
        menu.append(edit_item)

        remove_item = Gtk.MenuItem(label="Remove")
        remove_item.connect("activate", lambda *_: self._on_remove())
        menu.append(remove_item)

        menu.show_all()
        menu.popup_at_pointer(None)

    def _on_play_clicked(self, _button: Gtk.Button, channel_id: str) -> None:
        if self._playing_id == channel_id:
            self._on_stop()
        else:
            self._on_play(channel_id)

    def _on_row_selected(self, _listbox: Gtk.ListBox, _row: Optional[Gtk.ListBoxRow]) -> None:
        self._update_play_buttons()

    def _update_play_buttons(self) -> None:
        selected = self.list_box.get_selected_row()
        for row, meta in self._rows.items():
            if row is selected:
                is_playing = self._playing_id == meta.channel_id
                icon = _STOP_ICON if is_playing else _PLAY_ICON
                meta.play_image.set_from_icon_name(icon, Gtk.IconSize.BUTTON)
                meta.play_image.set_pixel_size(16)
                meta.play_btn.set_tooltip_text("Stop" if is_playing else "Play")
                meta.play_btn.set_opacity(1.0)
                meta.play_btn.set_sensitive(True)
            else:
                meta.play_btn.set_opacity(0.0)
                meta.play_btn.set_sensitive(False)
