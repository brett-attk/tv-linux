# TV App

GTK 3 + Python television front-end that embeds **libmpv** for playback. Channels are HDHomeRun-style HTTP MPEG-TS URLs (for example `http://192.168.1.27:5004/auto/v2.1`).

Licensed under the [MIT License](LICENSE).

## Features

- Left pane: channel list with friendly names; right-click for Favorite / Edit / Remove
- Favorites sort to the top of the list and show a heart icon
- Settings menu: add a channel or import from an HDHomeRun device lineup
- Right pane: embedded mpv video
- Channel Prev / Next, volume, mute, fullscreen
- Channels / favorites stored only on the local machine in `~/.config/tv-app/channels.json` (created empty on first run; not shipped in the repo)
- Settings (e.g. OSC on/off) stored in `~/.config/tv-app/settings.json`
- Errors logged to `~/.local/state/tv-app/error.log` (rotated)

## Setup

### System packages (Debian/Ubuntu)

```bash
sudo apt install python3 python3-venv python3-gi gir1.2-gtk-3.0 libmpv2 libmpv-dev
```

| Package | Why |
|---------|-----|
| `python3-gi` / `gir1.2-gtk-3.0` | GTK 3 bindings for the UI |
| `libmpv2` | libmpv shared library used for playback |
| `libmpv-dev` | Provides the `libmpv.so` symlink that `python-mpv` loads |
| `python3-venv` | Creates the project virtualenv |

### Python environment

`--system-site-packages` is required so the venv can import distro `python3-gi` / GTK:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` installs `python-mpv` (ctypes wrapper around libmpv). It does **not** replace the system `libmpv2` package.

## Run

`run.sh` forces `GDK_BACKEND=x11` so mpv can embed via an X11 window id (needed on Wayland via XWayland):

```bash
./run.sh
```

Or:

```bash
GDK_BACKEND=x11 .venv/bin/python -m tv_app
```

## Controls

| Action | UI | Keys |
|--------|----|------|
| Play channel | Play icon on selected row | — |
| Stop channel | Stop icon on selected playing row | — |
| Add channel | Settings → Add Channel… | — |
| Favorite channel | Right-click channel → Favorite this channel / Remove from favorites | — |
| Edit / Remove channel | Right-click channel → Edit / Remove | — |
| Import HDHomeRun | Settings → Import from HDHomeRun… → enter device URL → Fetch → select channels | — |
| Previous / next channel | Prev / Next | Page Up / Page Down |
| Volume | Vol − / Vol + | `-` / `+` |
| Mute | Mute | `m` |
| On-screen controls (mpv OSC) | OSC toggle (persisted) | — |
| Fullscreen | Fullscreen | `f` / Esc to exit |

### HDHomeRun import

1. Open **Settings → Import from HDHomeRun…**
2. Enter the device address (examples: `192.168.1.27`, `http://hdhomerun.local`, or `http://192.168.1.27/lineup.json`)
3. Click **Fetch** to load the lineup
4. Check the channels to add, then **Add selected**

Channels already in your list (same stream URL) are marked and skipped.

## Layout

```
tv_app/
  __main__.py       python -m tv_app entry (logging + GDK_BACKEND)
  app.py            Gtk.Application entry
  window.py         window coordinator (playback, fullscreen, keys)
  player.py         libmpv wrapper (worker thread)
  channel_store.py  channel list persistence
  settings.py       persisted preferences (OSC)
  paths.py          XDG config / state paths
  logging_setup.py  rotating error log
  hdhomerun.py      device lineup client
  ui/               channel list, transport bar, dialogs
tests/              unit tests (no display required)
```

## Tests

```bash
.venv/bin/python -m unittest discover -s tests
```

## Troubleshooting

HDHomeRun import and other failures show a short message in the UI and write details (timeouts, DNS, connection refused, HTTP errors, stack traces) to:

```bash
~/.local/state/tv-app/error.log
```

Override locations with `XDG_CONFIG_HOME` (channels/settings) or `XDG_STATE_HOME` (error log) if needed.

If video fails to embed, confirm you launched with X11 (`./run.sh` or `GDK_BACKEND=x11`) and that `libmpv2` / `libmpv-dev` are installed.

## Channel format

Each channel has a **friendly name** (shown in the list), a stream **URL**, and an optional **favorite** flag:

```json
{
  "channels": [
    {
      "id": "...",
      "name": "Channel 2.1",
      "url": "http://192.168.1.27:5004/auto/v2.1",
      "favorite": false
    }
  ]
}
```
