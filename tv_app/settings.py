"""Persisted app settings (JSON under XDG config)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .logging_setup import get_logger
from .paths import SETTINGS_FILE

log = get_logger(__name__)


@dataclass
class AppSettings:
    """User preferences that survive app restarts."""

    osc_enabled: bool = True

    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> "AppSettings":
        if not path.exists():
            settings = cls()
            try:
                settings.save(path)
            except OSError:
                log.exception("Failed to create default settings at %s", path)
            return settings
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                log.error("Settings file %s is not a JSON object; using defaults", path)
                return cls()
            return cls(osc_enabled=bool(data.get("osc_enabled", True)))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            log.exception("Failed to load settings from %s; using defaults", path)
            return cls()

    def save(self, path: Path = SETTINGS_FILE) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload: dict[str, Any] = asdict(self)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            tmp.replace(path)
        except OSError:
            log.exception("Failed to save settings to %s", path)
            raise
