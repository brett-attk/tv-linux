"""Gtk.Application entry for the TV app."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .theme import init_color_scheme
from .window import MainWindow


class TvApplication(Gtk.Application):
    APP_ID = "com.project.tv"

    def __init__(self) -> None:
        super().__init__(application_id=self.APP_ID)

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        # Follow the desktop Appearance light/dark preference (and live updates).
        init_color_scheme()

    def do_activate(self) -> None:
        win = self.props.active_window
        if win is None:
            win = MainWindow(self)
        else:
            win.show_all()
        win.present()


def run(argv=None) -> int:
    app = TvApplication()
    return app.run(argv)
