"""python -m tv_app entry point."""

from __future__ import annotations

import os
import sys


def main() -> None:
    # Prefer X11 so mpv can embed via window id (needed under Wayland).
    os.environ.setdefault("GDK_BACKEND", "x11")
    from .app import run

    sys.exit(run(sys.argv))


if __name__ == "__main__":
    main()
