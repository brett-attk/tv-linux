"""Channel model and JSON persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from .paths import CHANNELS_FILE


@dataclass
class Channel:
    name: str
    url: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


def default_channels() -> List[Channel]:
    """Fresh installs start empty; channels are added or imported by the user."""
    return []


class ChannelStore:
    """In-memory channel list with atomic JSON saves."""

    def __init__(self, path: Path = CHANNELS_FILE) -> None:
        self.path = path
        self.channels: List[Channel] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.channels = default_channels()
            self.save()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data.get("channels", data if isinstance(data, list) else [])
            loaded: List[Channel] = []
            for item in items:
                name = (item.get("name") or "").strip()
                url = (item.get("url") or "").strip()
                if not name or not url:
                    continue
                loaded.append(
                    Channel(
                        id=item.get("id") or uuid.uuid4().hex,
                        name=name,
                        url=url,
                    )
                )
            self.channels = loaded if loaded else default_channels()
            if not loaded:
                self.save()
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            self.channels = default_channels()
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"channels": [asdict(c) for c in self.channels]}
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> List[Channel]:
        return list(self.channels)

    def get(self, channel_id: str) -> Optional[Channel]:
        for channel in self.channels:
            if channel.id == channel_id:
                return channel
        return None

    def index_of(self, channel_id: str) -> int:
        for i, channel in enumerate(self.channels):
            if channel.id == channel_id:
                return i
        return -1

    def add(self, name: str, url: str) -> Channel:
        channel = Channel(name=name.strip(), url=url.strip())
        self.channels.append(channel)
        self.save()
        return channel

    def update(self, channel_id: str, name: str, url: str) -> Optional[Channel]:
        channel = self.get(channel_id)
        if channel is None:
            return None
        channel.name = name.strip()
        channel.url = url.strip()
        self.save()
        return channel

    def remove(self, channel_id: str) -> bool:
        before = len(self.channels)
        self.channels = [c for c in self.channels if c.id != channel_id]
        if len(self.channels) == before:
            return False
        self.save()
        return True

    def neighbor(self, channel_id: str, delta: int) -> Optional[Channel]:
        if not self.channels:
            return None
        idx = self.index_of(channel_id)
        if idx < 0:
            return self.channels[0]
        return self.channels[(idx + delta) % len(self.channels)]
