"""Thin wrapper around python-mpv / libmpv for embedded playback.

All libmpv calls that can block (load/stop/property writes) run on a dedicated
worker thread so the GTK main loop stays responsive.
"""

from __future__ import annotations

import queue
import threading
from functools import partial
from typing import Callable, Optional

import mpv


class MpvPlayer:
    def __init__(self, osc_enabled: bool = True) -> None:
        self._player: Optional[mpv.MPV] = None
        self._on_fullscreen: Optional[Callable[[bool], None]] = None
        self._volume: int = 80
        self._muted: bool = False
        self._fullscreen: bool = False
        self._osc_enabled: bool = bool(osc_enabled)

        self._lock = threading.Lock()
        # Latest desired media target; None means stopped/idle.
        self._media_url: Optional[str] = None
        self._media_gen: int = 0

        self._jobs: queue.Queue[Optional[Callable[[], None]]] = queue.Queue()
        self._thread = threading.Thread(
            target=self._run_worker,
            name="mpv-worker",
            daemon=True,
        )
        self._thread.start()

    @property
    def ready(self) -> bool:
        return self._player is not None

    def _run_worker(self) -> None:
        while True:
            job = self._jobs.get()
            try:
                if job is None:
                    break
                job()
            except Exception:
                # Never let a failed mpv call kill the worker thread.
                pass
            finally:
                self._jobs.task_done()

    def _submit(self, job: Callable[[], None]) -> None:
        self._jobs.put(job)

    def attach(self, wid: int) -> None:
        """Embed libmpv into an existing X11 window (no separate mpv window).

        Construction stays on the caller (GTK realize) so the wid/X11 setup is
        ready before play(); subsequent control goes through the worker thread.
        """
        if self._player is not None:
            return
        # vo=x11 + wid keeps video inside the GTK DrawingArea/EventBox.
        # idle=yes keeps the player alive without opening a window until play().
        self._player = mpv.MPV(
            wid=int(wid),
            vo="x11",
            force_window=False,
            idle=True,
            input_default_bindings=True,
            input_vo_keyboard=True,
            osc=self._osc_enabled,
            # Keep the GTK host window's geometry; letterbox inside the embed.
            keepaspect=True,
            keepaspect_window=False,
            # Live tuner streams: keep buffering light for snappy channel changes.
            cache="yes",
            demuxer_max_bytes="8MiB",
            demuxer_readahead_secs="1.5",
            volume=self._volume,
        )
        self._player.observe_property("fullscreen", self._fullscreen_changed)
        # Apply any volume/mute that was set before attach.
        self._submit(self._apply_audio_state)
        self._submit(self._apply_osc)

    def _fullscreen_changed(self, _name, value) -> None:
        if value is None:
            return
        self._fullscreen = bool(value)
        if self._on_fullscreen is not None:
            self._on_fullscreen(bool(value))

    def set_fullscreen_handler(self, handler: Callable[[bool], None]) -> None:
        self._on_fullscreen = handler

    def play(self, url: str) -> None:
        """Request playback of url; returns immediately (worker applies it)."""
        with self._lock:
            self._media_url = url
            self._media_gen += 1
            gen = self._media_gen
        self._submit(partial(self._apply_media, gen))

    def stop(self) -> None:
        """Request stop; returns immediately (worker applies it)."""
        with self._lock:
            self._media_url = None
            self._media_gen += 1
            gen = self._media_gen
        self._submit(partial(self._apply_media, gen))

    def _apply_media(self, gen: int) -> None:
        with self._lock:
            if gen != self._media_gen:
                return
            url = self._media_url
            player = self._player
        if player is None:
            return
        # Use async libmpv commands so a slow HTTP teardown cannot stall the
        # worker behind a superseded play/stop request.
        try:
            if url:
                player.command_async("loadfile", url, "replace")
            else:
                player.command_async("stop")
        except Exception:
            # Fallback to synchronous API if async is unavailable.
            if url:
                player.play(url)
            else:
                player.command("stop")

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, int(volume)))
        self._submit(self._apply_audio_state)

    def volume_up(self, step: int = 5) -> int:
        self.set_volume(self._volume + step)
        return self._volume

    def volume_down(self, step: int = 5) -> int:
        self.set_volume(self._volume - step)
        return self._volume

    def set_mute(self, muted: bool) -> bool:
        self._muted = bool(muted)
        self._submit(self._apply_audio_state)
        return self._muted

    def mute_toggle(self) -> bool:
        return self.set_mute(not self._muted)

    def _apply_audio_state(self) -> None:
        player = self._player
        if player is None:
            return
        player.volume = self._volume
        player.mute = self._muted

    def set_osc_enabled(self, enabled: bool) -> bool:
        """Enable/disable mpv on-screen controls (OSC). Returns immediately."""
        self._osc_enabled = bool(enabled)
        self._submit(self._apply_osc)
        return self._osc_enabled

    def _apply_osc(self) -> None:
        player = self._player
        if player is None:
            return
        try:
            player.osc = self._osc_enabled
        except Exception:
            try:
                player["osc"] = self._osc_enabled
            except Exception:
                pass
        # Force OSC to hide immediately when disabled (visibility may linger otherwise).
        try:
            if self._osc_enabled:
                player.command("script-message", "osc-visibility", "auto", "no-osd")
            else:
                player.command("script-message", "osc-visibility", "never", "no-osd")
        except Exception:
            pass

    @property
    def osc_enabled(self) -> bool:
        return self._osc_enabled

    @property
    def volume(self) -> int:
        return self._volume

    @property
    def muted(self) -> bool:
        return self._muted

    def set_fullscreen(self, enabled: bool) -> None:
        self._fullscreen = bool(enabled)
        self._submit(partial(self._apply_fullscreen, self._fullscreen))

    def _apply_fullscreen(self, enabled: bool) -> None:
        player = self._player
        if player is None:
            return
        # With wid embedding, avoid mpv's own fullscreen window; the GTK
        # window handles fullscreen UI. Keep property in sync when possible.
        try:
            player.fullscreen = bool(enabled)
        except Exception:
            pass

    def toggle_fullscreen(self) -> bool:
        self.set_fullscreen(not self._fullscreen)
        return self._fullscreen

    def shutdown(self) -> None:
        """Tear down mpv on the worker thread without blocking the UI for long."""
        with self._lock:
            self._media_url = None
            self._media_gen += 1

        done = threading.Event()

        def _terminate() -> None:
            player = self._player
            self._player = None
            if player is not None:
                try:
                    # quit is usually faster / safer than terminate from UI teardown.
                    player.quit()
                except Exception:
                    pass
                try:
                    player.terminate()
                except Exception:
                    pass
            done.set()

        self._submit(_terminate)
        self._jobs.put(None)
        # Brief wait only — never hang app exit on a stuck stream.
        done.wait(timeout=1.5)
        self._thread.join(timeout=0.5)
