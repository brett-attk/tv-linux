"""XDG config / state locations shared by persistence modules."""

from __future__ import annotations

import os
from pathlib import Path


CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "tv-app"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "tv-app"

CHANNELS_FILE = CONFIG_DIR / "channels.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
ERROR_LOG_FILE = STATE_DIR / "error.log"
