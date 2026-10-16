"""Add / Edit channel dialogs and About."""

from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .. import __version__
from ..channel_store import Channel

_GITHUB_URL = "https://github.com/brett-attk/tv-linux"


def _valid_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


class ChannelDialog(Gtk.Dialog):
    def __init__(
        self,
        parent: Gtk.Window,
        title: str,
        channel: Optional[Channel] = None,
    ) -> None:
        super().__init__(title=title, transient_for=parent, modal=True)
        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK,
            Gtk.ResponseType.OK,
        )
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_resizable(False)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8, margin=12)
        self.get_content_area().add(grid)

        name_label = Gtk.Label(label="Channel name:", xalign=0)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_placeholder_text("NBC")
        self.name_entry.set_hexpand(True)
        self.name_entry.set_activates_default(True)

        url_label = Gtk.Label(label="URL:", xalign=0)
        self.url_entry = Gtk.Entry()
        self.url_entry.set_placeholder_text("http://192.168.1.27:5004/auto/v2.1")
        self.url_entry.set_width_chars(42)
        self.url_entry.set_hexpand(True)
        self.url_entry.set_activates_default(True)

        if channel is not None:
            self.name_entry.set_text(channel.name)
            self.url_entry.set_text(channel.url)

        grid.attach(name_label, 0, 0, 1, 1)
        grid.attach(self.name_entry, 1, 0, 1, 1)
        grid.attach(url_label, 0, 1, 1, 1)
        grid.attach(self.url_entry, 1, 1, 1, 1)

        self.error_label = Gtk.Label(xalign=0)
        self.error_label.get_style_context().add_class("error")
        self.error_label.set_no_show_all(True)
        grid.attach(self.error_label, 0, 2, 2, 1)

        self.show_all()

    def get_values(self) -> Optional[Tuple[str, str]]:
        name = self.name_entry.get_text().strip()
        url = self.url_entry.get_text().strip()
        if not name:
            self.error_label.set_text("Enter a channel name.")
            self.error_label.show()
            return None
        if not _valid_url(url):
            self.error_label.set_text("Enter an http:// or https:// URL.")
            self.error_label.show()
            return None
        return name, url


def confirm_remove(parent: Gtk.Window, channel_name: str) -> bool:
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text=f'Remove channel "{channel_name}"?',
    )
    dialog.add_buttons(
        Gtk.STOCK_CANCEL,
        Gtk.ResponseType.CANCEL,
        "Remove",
        Gtk.ResponseType.OK,
    )
    response = dialog.run()
    dialog.destroy()
    return response == Gtk.ResponseType.OK


def _polish_about_dialog(dialog: Gtk.AboutDialog) -> None:
    """Hide the default logo and disable text-selection cursors on labels."""
    dialog.set_logo(None)
    dialog.set_logo_icon_name("")

    def walk(widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.Image):
            widget.hide()
            widget.set_no_show_all(True)
        elif isinstance(widget, Gtk.Label):
            widget.set_selectable(False)
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                walk(child)

    walk(dialog)


def show_about(parent: Gtk.Window) -> None:
    dialog = Gtk.AboutDialog(
        transient_for=parent,
        modal=True,
        program_name="TV",
        version=__version__,
        comments="GTK television front-end with embedded mpv playback.",
        website=_GITHUB_URL,
        website_label="GitHub repository",
        license_type=Gtk.License.MIT_X11,
        copyright="Licensed under the MIT License",
    )
    _polish_about_dialog(dialog)
    dialog.run()
    dialog.destroy()
