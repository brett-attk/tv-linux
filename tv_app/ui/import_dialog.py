"""HDHomeRun lineup import dialog."""

from __future__ import annotations

import threading
from typing import Callable, Iterable, List, Optional, Set, TypeVar

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from ..hdhomerun import HdhrChannel, HdhrError, fetch_lineup
from ..logging_setup import get_logger, log_path

log = get_logger(__name__)

T = TypeVar("T")


def apply_if_open(closed: bool, callback: Callable[..., T], *args) -> Optional[T]:
    """Run ``callback`` only when the dialog is still open.

    Used so background fetch completions are ignored after destroy.
    """
    if closed:
        return None
    return callback(*args)


class HdhrImportDialog(Gtk.Dialog):
    """Fetch an HDHomeRun lineup and let the user pick channels to add."""

    def __init__(
        self,
        parent: Gtk.Window,
        existing_urls: Optional[Iterable[str]] = None,
    ) -> None:
        super().__init__(
            title="Import from HDHomeRun",
            transient_for=parent,
            modal=True,
        )
        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            "Add selected",
            Gtk.ResponseType.OK,
        )
        self.set_default_size(480, 520)
        self.set_default_response(Gtk.ResponseType.OK)

        self._existing_urls: Set[str] = {u.strip() for u in (existing_urls or []) if u.strip()}
        self._channels: List[HdhrChannel] = []
        self._checks: List[Gtk.CheckButton] = []
        self._fetching = False
        self._closed = False
        self.connect("destroy", self._on_destroyed)

        content = self.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        url_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        url_label = Gtk.Label(label="Device URL:", xalign=0)
        self.url_entry = Gtk.Entry()
        self.url_entry.set_placeholder_text("http://192.168.1.27 or hdhomerun.local")
        self.url_entry.set_hexpand(True)
        self.url_entry.set_activates_default(False)
        self.url_entry.connect("activate", self._on_fetch_clicked)
        self.fetch_btn = Gtk.Button(label="Fetch")
        self.fetch_btn.connect("clicked", self._on_fetch_clicked)
        url_row.pack_start(url_label, False, False, 0)
        url_row.pack_start(self.url_entry, True, True, 0)
        url_row.pack_start(self.fetch_btn, False, False, 0)
        content.pack_start(url_row, False, False, 0)

        self.status_label = Gtk.Label(xalign=0)
        self.status_label.set_line_wrap(True)
        self.status_label.set_text("Enter the HDHomeRun address and click Fetch.")
        content.pack_start(self.status_label, False, False, 0)

        select_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.select_all_btn = Gtk.Button(label="Select all")
        self.select_none_btn = Gtk.Button(label="Select none")
        self.select_all_btn.connect("clicked", lambda *_: self._set_all_checks(True))
        self.select_none_btn.connect("clicked", lambda *_: self._set_all_checks(False))
        self.select_all_btn.set_sensitive(False)
        self.select_none_btn.set_sensitive(False)
        select_row.pack_start(self.select_all_btn, False, False, 0)
        select_row.pack_start(self.select_none_btn, False, False, 0)
        content.pack_start(select_row, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(300)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.add(self.list_box)
        content.pack_start(scrolled, True, True, 0)

        self.show_all()
        self._update_ok_sensitivity()

    def _on_destroyed(self, *_args) -> None:
        self._closed = True

    def _on_fetch_clicked(self, *_args) -> None:
        if self._fetching or self._closed:
            return
        url = self.url_entry.get_text().strip()
        if not url:
            self.status_label.set_text("Enter an HDHomeRun device URL or IP address.")
            return

        self._fetching = True
        self.fetch_btn.set_sensitive(False)
        self.url_entry.set_sensitive(False)
        self.status_label.set_text("Fetching lineup…")
        self._clear_list()

        def worker() -> None:
            try:
                channels = fetch_lineup(url)
            except HdhrError as exc:
                log.error(
                    "HDHomeRun import failed for %r: %s (details in %s)",
                    url,
                    exc,
                    log_path(),
                )
                GLib.idle_add(self._idle_fetch_failed, str(exc))
                return
            except Exception as exc:  # noqa: BLE001 - surface unexpected fetch errors in UI
                log.exception("Unexpected HDHomeRun import failure for %r", url)
                GLib.idle_add(
                    self._idle_fetch_failed,
                    f"Unexpected error: {exc}. See {log_path()}.",
                )
                return
            GLib.idle_add(self._idle_fetch_ok, channels)

        threading.Thread(target=worker, daemon=True, name="hdhr-fetch").start()

    def _idle_fetch_failed(self, message: str) -> bool:
        apply_if_open(self._closed, self._on_fetch_failed, message)
        return False

    def _idle_fetch_ok(self, channels: List[HdhrChannel]) -> bool:
        apply_if_open(self._closed, self._on_fetch_ok, channels)
        return False

    def _on_fetch_failed(self, message: str) -> bool:
        self._fetching = False
        self.fetch_btn.set_sensitive(True)
        self.url_entry.set_sensitive(True)
        self.status_label.set_text(f"{message}\nDetails: {log_path()}")
        self.select_all_btn.set_sensitive(False)
        self.select_none_btn.set_sensitive(False)
        self._update_ok_sensitivity()
        return False

    def _on_fetch_ok(self, channels: List[HdhrChannel]) -> bool:
        self._fetching = False
        self.fetch_btn.set_sensitive(True)
        self.url_entry.set_sensitive(True)
        self._channels = list(channels)
        self._populate_list()
        already = sum(1 for c in self._channels if c.url in self._existing_urls)
        self.status_label.set_text(
            f"Found {len(self._channels)} channel(s)"
            + (f" ({already} already in your list)." if already else ".")
        )
        self.select_all_btn.set_sensitive(True)
        self.select_none_btn.set_sensitive(True)
        self._update_ok_sensitivity()
        return False

    def _clear_list(self) -> None:
        self._channels = []
        self._checks = []
        for child in self.list_box.get_children():
            self.list_box.remove(child)

    def _populate_list(self) -> None:
        self._checks = []
        for child in self.list_box.get_children():
            self.list_box.remove(child)

        for channel in self._channels:
            row = Gtk.ListBoxRow()
            row.set_activatable(False)
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.set_margin_top(4)
            box.set_margin_bottom(4)

            check = Gtk.CheckButton()
            already = channel.url in self._existing_urls
            if already:
                check.set_active(True)
                check.set_sensitive(False)
                check.set_tooltip_text("Already in your channel list")
            else:
                check.set_active(False)
                check.connect("toggled", lambda *_: self._update_ok_sensitivity())

            label = Gtk.Label(label=channel.display_name, xalign=0)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_hexpand(True)
            if already:
                label.set_text(f"{channel.display_name}  — already added")

            box.pack_start(check, False, False, 0)
            box.pack_start(label, True, True, 0)
            row.add(box)
            self.list_box.add(row)
            self._checks.append(check)

        self.list_box.show_all()

    def _set_all_checks(self, active: bool) -> None:
        for check in self._checks:
            if check.get_sensitive():
                check.set_active(active)
        self._update_ok_sensitivity()

    def _update_ok_sensitivity(self) -> None:
        ok = self.get_widget_for_response(Gtk.ResponseType.OK)
        if ok is not None:
            ok.set_sensitive(bool(self.get_selected_channels()))

    def get_selected_channels(self) -> List[HdhrChannel]:
        selected: List[HdhrChannel] = []
        for channel, check in zip(self._channels, self._checks):
            if channel.url in self._existing_urls:
                continue
            if check.get_active():
                selected.append(channel)
        return selected
