"""Follow the desktop light/dark preference in GTK 3."""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gio, Gtk

from .logging_setup import get_logger

log = get_logger(__name__)

_SCHEMA_ID = "org.gnome.desktop.interface"
_COLOR_SCHEME_KEY = "color-scheme"
_watched_settings: Optional[Gio.Settings] = None


def _gnome_color_scheme() -> Optional[str]:
    source = Gio.SettingsSchemaSource.get_default()
    if source is None:
        return None
    schema = source.lookup(_SCHEMA_ID, True)
    if schema is None or not schema.has_key(_COLOR_SCHEME_KEY):
        return None
    return Gio.Settings.new(_SCHEMA_ID).get_string(_COLOR_SCHEME_KEY)


def _prefers_dark() -> Optional[bool]:
    """Return True/False from the desktop preference, or None if unknown."""
    scheme = _gnome_color_scheme()
    if scheme is None:
        return None
    if scheme == "prefer-dark":
        return True
    if scheme in ("prefer-light", "default"):
        return False
    return None


def apply_color_scheme() -> None:
    """Apply the system color scheme to this process's GTK settings."""
    gtk_settings = Gtk.Settings.get_default()
    if gtk_settings is None:
        return
    prefers = _prefers_dark()
    if prefers is None:
        log.info("No desktop color-scheme preference available; using GTK defaults")
        return
    current = bool(gtk_settings.get_property("gtk-application-prefer-dark-theme"))
    if current != prefers:
        gtk_settings.set_property("gtk-application-prefer-dark-theme", prefers)
        log.info("gtk-application-prefer-dark-theme=%s", prefers)


def init_color_scheme() -> None:
    """Apply the current preference and watch for desktop Appearance changes."""
    global _watched_settings

    apply_color_scheme()

    source = Gio.SettingsSchemaSource.get_default()
    if source is None:
        return
    schema = source.lookup(_SCHEMA_ID, True)
    if schema is None or not schema.has_key(_COLOR_SCHEME_KEY):
        return

    _watched_settings = Gio.Settings.new(_SCHEMA_ID)

    def _on_changed(_settings: Gio.Settings, key: str) -> None:
        if key == _COLOR_SCHEME_KEY:
            apply_color_scheme()

    _watched_settings.connect("changed", _on_changed)
