#!/usr/bin/env bash
# Embedded mpv uses X11 window IDs; force XWayland on Wayland sessions.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export GDK_BACKEND=x11
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" -m tv_app "$@"
fi
exec python3 -m tv_app "$@"
