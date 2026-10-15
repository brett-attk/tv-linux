# TV App

GTK 3 + Python television front-end that embeds **mpv** for playback. Channels are HDHomeRun-style HTTP MPEG-TS URLs (for example `http://192.168.1.27:5004/auto/v2.1`).

Licensed under the [MIT License](LICENSE).

## Features

- Left pane: channel list with friendly names; Add / Edit / Remove / Import
- Import channels from an HDHomeRun device lineup (device IP or URL)
- Right pane: embedded mpv video
- Channel Prev / Next, volume, mute, fullscreen
- Channels stored in `~/.config/tv-app/channels.json`
- Settings (e.g. OSC on/off) stored in `~/.config/tv-app/settings.json`

## Dependencies

System packages (Debian/Ubuntu):

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 libmpv2 libmpv-dev
```

Python package (venv recommended):

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

`--system-site-packages` is required so the venv can use distro `python3-gi` / GTK bindings.

## Run

On Wayland sessions the launcher forces X11 (XWayland) so mpv can embed into the video area:

```bash
chmod +x run.sh
./run.sh
```

Or:

```bash
GDK_BACKEND=x11 .venv/bin/python -m tv_app
```

## Controls

| Action | UI | Keys |
|--------|----|------|
| Play channel | Play icon on highlighted row | — |
| Stop channel | Stop icon on highlighted playing row | — |
| Import HDHomeRun | Import → enter device URL → Fetch → select channels | — |
| Previous / next channel | Prev / Next | Page Up / Page Down |
| Volume | Vol − / Vol + | `-` / `+` |
| Mute | Mute | `m` |
| On-screen controls (mpv OSC) | OSC toggle (persisted) | — |
| Fullscreen | Fullscreen | `f` / Esc to exit |

### HDHomeRun import

1. Click **Import**
2. Enter the device address (examples: `192.168.1.27`, `http://hdhomerun.local`, or `http://192.168.1.27/lineup.json`)
3. Click **Fetch** to load the lineup
4. Check the channels to add, then **Add selected**

Channels already in your list (same stream URL) are marked and skipped.

## Layout

```
tv_app/
  app.py            Gtk.Application entry
  window.py         window coordinator (playback, fullscreen, keys)
  player.py         libmpv wrapper (worker thread)
  channel_store.py  channel list persistence
  settings.py       persisted preferences (OSC)
  hdhomerun.py      device lineup client
  ui/               channel list, transport bar, dialogs
tests/              unit tests (no display required)
```

## Tests

```bash
.venv/bin/python -m unittest discover -s tests
```

## Channel format

Each channel has a **friendly name** (shown in the list) and a stream **URL**:

```json
{
  "channels": [
    {
      "id": "...",
      "name": "Channel 2.1",
      "url": "http://192.168.1.27:5004/auto/v2.1"
    }
  ]
}
```
