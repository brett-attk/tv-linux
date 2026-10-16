"""Channel model and JSON persistence."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from .logging_setup import get_logger
from .paths import CHANNELS_FILE

log = get_logger(__name__)


@dataclass
class Channel:
    name: str
    url: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    favorite: bool = False


class ChannelStore:
    """In-memory channel list with atomic JSON saves."""

    def __init__(self, path: Path = CHANNELS_FILE) -> None:
        self.path = path
        self.channels: List[Channel] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.channels = []
            self.save()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data.get("channels", data if isinstance(data, list) else [])
            loaded: List[Channel] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = (item.get("name") or "").strip()
                url = (item.get("url") or "").strip()
                if not name or not url:
                    continue
                loaded.append(
                    Channel(
                        id=item.get("id") or uuid.uuid4().hex,
                        name=name,
                        url=url,
                        favorite=bool(item.get("favorite", False)),
                    )
                )
            self.channels = loaded
            if not loaded:
                self.save()
            log.info("Loaded %s channel(s) from %s", len(self.channels), self.path)
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            log.exception("Failed to load channels from %s; starting empty", self.path)
            self.channels = []
            try:
                self.save()
            except OSError:
                log.exception("Failed to rewrite channels file after load error")

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"channels": [asdict(c) for c in self.channels]}
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            log.exception("Failed to save channels to %s", self.path)
            raise

    def list(self) -> List[Channel]:
        """Favorites first (stable), then non-favorites in storage order."""
        favorites = [c for c in self.channels if c.favorite]
        others = [c for c in self.channels if not c.favorite]
        return favorites + others

    def get(self, channel_id: str) -> Optional[Channel]:
        for channel in self.channels:
            if channel.id == channel_id:
                return channel
        return None

    def index_of(self, channel_id: str) -> int:
        """Index in display order (favorites first)."""
        return next(
            (i for i, channel in enumerate(self.list()) if channel.id == channel_id),
            -1,
        )

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

    def set_favorite(self, channel_id: str, favorite: bool) -> Optional[Channel]:
        channel = self.get(channel_id)
        if channel is None:
            return None
        channel.favorite = favorite
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
        channels = self.list()
        if not channels:
            return None
        idx = next((i for i, c in enumerate(channels) if c.id == channel_id), -1)
        if idx < 0:
            return channels[0]
        return channels[(idx + delta) % len(channels)]
