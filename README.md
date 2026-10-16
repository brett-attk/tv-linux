# TV App

GTK 3 + Python television front-end that embeds **libmpv** for playback. Channels are HDHomeRun-style HTTP MPEG-TS URLs (for example `http://192.168.1.27:5004/auto/v2.1`).

Licensed under the [MIT License](LICENSE).

## Features

- Left pane: channel list with friendly names; right-click for Favorite / Edit / Remove
- Favorites sort to the top of the list and show a heart icon
- Settings menu: add a channel or import from an HDHomeRun device lineup
- Right pane: embedded mpv video
- Channel Prev / Next, volume, mute, fullscreen
- Local-only persistence under XDG paths (see [Where data is stored](#where-data-is-stored))

## Where data is stored

Nothing from your channel list is shipped in the git repo. On first launch the app creates the config directory and empty files as needed.

| What | File | Notes |
|------|------|--------|
| **Channel list + favorites** | `~/.config/tv-app/channels.json` | Updated whenever you add, edit, remove, import, or favorite a channel |
| **App settings** (e.g. OSC on/off) | `~/.config/tv-app/settings.json` | Preferences that survive restarts |
| **Error log** | `~/.local/state/tv-app/error.log` | Rotating log for import/network and other failures |

Paths follow the XDG Base Directory spec:

- Config (channels + settings): `$XDG_CONFIG_HOME/tv-app/` — defaults to `~/.config/tv-app/`
- State (error log): `$XDG_STATE_HOME/tv-app/` — defaults to `~/.local/state/tv-app/`

```bash
# Inspect your channel list
less ~/.config/tv-app/channels.json

# Inspect settings
less ~/.config/tv-app/settings.json

# Inspect the error log
less ~/.local/state/tv-app/error.log
```

## Install (Debian/Ubuntu)

Do these steps once, from a terminal, in the project directory.

### 1. Get the code

```bash
git clone https://github.com/brett-attk/tv-linux.git
cd tv-linux
```

### 2. Install system packages

```bash
sudo apt update
sudo apt install python3 python3-venv python3-gi gir1.2-gtk-3.0 libmpv2 libmpv-dev
```

These provide Python, GTK 3, and libmpv (needed for the UI and video).

### 3. Create the Python environment

`--system-site-packages` is required so the app can use the system GTK packages from step 2:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

This installs `python-mpv` into `.venv`. It does not replace the system `libmpv2` package.

### 4. Run the app

```bash
./run.sh
```

`run.sh` starts the app with X11 embedding enabled (needed for video on Wayland).

On first launch the channel list is empty. Add channels with **Settings → Add Channel…** or **Settings → Import from HDHomeRun…**. Your list is saved only on this machine in `~/.config/tv-app/channels.json` (see [Where data is stored](#where-data-is-stored)).

**Later launches:** from the project directory, just run `./run.sh` again (no reinstall needed).

**Alternative launch** (same as `./run.sh`):

```bash
GDK_BACKEND=x11 .venv/bin/python -m tv_app
```

## Controls

| Action | UI | Keys |
|--------|----|------|
| Play channel | Play icon on selected row | — |
| Stop channel | Stop icon on selected playing row | — |
| Add channel | Settings → Add Channel… | — |
| About | Settings → About | — |
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

| Problem | What to check |
|---------|----------------|
| `ModuleNotFoundError: gi` or GTK errors | Re-run step 2, and recreate the venv with `--system-site-packages` (step 3) |
| `No module named mpv` / libmpv load errors | Install `libmpv2` and `libmpv-dev` (step 2), then `pip install -r requirements.txt` (step 3) |
| Black video / no picture | Launch with `./run.sh` (forces X11). Plain Wayland without X11 embedding will not work |
| Import / network errors | Details are written to `~/.local/state/tv-app/error.log` |

```bash
# View the error log
less ~/.local/state/tv-app/error.log
```

To relocate storage, set `XDG_CONFIG_HOME` and/or `XDG_STATE_HOME` before launching (see [Where data is stored](#where-data-is-stored)).

## Channel format

`~/.config/tv-app/channels.json` holds each channel’s **friendly name**, stream **URL**, and optional **favorite** flag:

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
