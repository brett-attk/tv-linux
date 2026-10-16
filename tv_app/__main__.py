"""python -m tv_app entry point."""

from __future__ import annotations

import os
import sys


def main() -> None:
    # Prefer X11 so mpv can embed via window id (needed under Wayland).
    os.environ.setdefault("GDK_BACKEND", "x11")

    # Configure logging before importing the rest of the app.
    from .logging_setup import get_logger, setup_logging

    log_file = setup_logging()
    log = get_logger(__name__)
    log.info("Starting tv-app (error log: %s)", log_file)

    from .app import run

    try:
        code = run(sys.argv)
    except Exception:
        log.exception("tv-app exited with an unhandled error")
        raise
    sys.exit(code)


if __name__ == "__main__":
    main()
