"""Channel list pane: hover-to-select rows and per-row play/stop."""

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
_BTN_SIZE = 28


@dataclass
class _Row:
    channel_id: str
    play_btn: Gtk.Button
    play_image: Gtk.Image


class ChannelListPane(Gtk.Box):
    """Left-hand channel list with Add / Edit / Remove / Import."""

    def __init__(
        self,
        on_play: PlayHandler,
        on_stop: StopHandler,
        on_add: ActionHandler,
        on_edit: ActionHandler,
        on_remove: ActionHandler,
        on_import: ActionHandler,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._on_play = on_play
        self._on_stop = on_stop
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
        scrolled.add(self.list_box)

        viewport = self.list_box.get_parent()
        if viewport is not None:
            viewport.add_events(
                Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK
            )
            viewport.connect("motion-notify-event", self._on_list_motion)
            viewport.connect("enter-notify-event", self._on_list_motion)
        self.pack_start(scrolled, True, True, 0)

        self.edit_btn = Gtk.Button(label="Edit")
        self.remove_btn = Gtk.Button(label="Remove")
        add_btn = Gtk.Button(label="Add")
        import_btn = Gtk.Button(label="Import")
        add_btn.connect("clicked", lambda *_: on_add())
        self.edit_btn.connect("clicked", lambda *_: on_edit())
        self.remove_btn.connect("clicked", lambda *_: on_remove())
        import_btn.connect("clicked", lambda *_: on_import())

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for button in (add_btn, self.edit_btn, self.remove_btn, import_btn):
            button.set_hexpand(True)
            btn_row.pack_start(button, True, True, 0)
        self.pack_start(btn_row, False, False, 0)
        self._update_edit_buttons()

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
        self._update_edit_buttons()
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

        hover = Gtk.EventBox()
        hover.set_visible_window(True)
        hover.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 0))
        hover.add(box)
        hover.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        hover.connect("enter-notify-event", self._on_hover, row)
        hover.connect("motion-notify-event", self._on_hover, row)
        play_btn.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        play_btn.connect("enter-notify-event", self._on_hover, row)
        play_btn.connect("motion-notify-event", self._on_hover, row)
        row.add(hover)

        self._rows[row] = _Row(channel.id, play_btn, image)
        return row

    def _on_play_clicked(self, _button: Gtk.Button, channel_id: str) -> None:
        if self._playing_id == channel_id:
            self._on_stop()
        else:
            self._on_play(channel_id)

    def _select_row(self, row: Optional[Gtk.ListBoxRow]) -> None:
        if row is not None and self.list_box.get_selected_row() is not row:
            self.list_box.select_row(row)

    def _on_hover(self, _widget: Gtk.Widget, _event: Gdk.Event, row: Gtk.ListBoxRow) -> bool:
        self._select_row(row)
        return False

    def _on_list_motion(self, viewport: Gtk.Widget, event: Gdk.Event) -> bool:
        ok, _x, y = viewport.translate_coordinates(self.list_box, int(event.x), int(event.y))
        if not ok:
            y = int(event.y)
        self._select_row(self.list_box.get_row_at_y(int(y)))
        return False

    def _on_row_selected(self, _listbox: Gtk.ListBox, _row: Optional[Gtk.ListBoxRow]) -> None:
        self._update_edit_buttons()
        self._update_play_buttons()

    def _update_edit_buttons(self) -> None:
        has = self.selected_id() is not None
        self.edit_btn.set_sensitive(has)
        self.remove_btn.set_sensitive(has)

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
