"""Persisted app settings (JSON under XDG config)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import SETTINGS_FILE


@dataclass
class AppSettings:
    """User preferences that survive app restarts."""

    osc_enabled: bool = True

    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> "AppSettings":
        if not path.exists():
            settings = cls()
            settings.save(path)
            return settings
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls()
            return cls(osc_enabled=bool(data.get("osc_enabled", True)))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return cls()

    def save(self, path: Path = SETTINGS_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = asdict(self)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
