"""HDHomeRun HTTP discover / lineup helpers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List, Sequence
from urllib.parse import urlparse, urlunparse


DEFAULT_TIMEOUT = 8.0


@dataclass(frozen=True)
class HdhrChannel:
    guide_number: str
    guide_name: str
    url: str
    tags: Sequence[str] = field(default_factory=tuple)

    @property
    def display_name(self) -> str:
        number = self.guide_number.strip()
        name = self.guide_name.strip()
        if number and name:
            label = f"{number}  {name}"
        elif number:
            label = number
        elif name:
            label = name
        else:
            label = self.url
        if self.has_drm:
            label = f"{label}  (DRM)"
        return label

    @property
    def has_drm(self) -> bool:
        return "drm" in {t.lower() for t in self.tags}


class HdhrError(Exception):
    """Raised when discover/lineup fetch fails."""


def normalize_device_url(user_input: str) -> str:
    """Accept IP/host, base URL, or lineup URL; return an http(s) base URL."""
    text = (user_input or "").strip()
    if not text:
        raise HdhrError("Enter an HDHomeRun device URL or IP address.")

    if "://" not in text:
        text = "http://" + text

    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HdhrError("Enter a valid http:// URL or IP address.")

    path = (parsed.path or "").rstrip("/")
    if path.endswith("/lineup.json") or path.endswith("/discover.json"):
        path = path.rsplit("/", 1)[0]

    # Drop query/fragment; keep host (and optional explicit port).
    base = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    return base.rstrip("/")


def _http_get_json(url: str, timeout: float) -> object:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "tv-app/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise HdhrError(f"HTTP {exc.code} fetching {url}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise HdhrError(f"Could not reach device: {reason}") from exc
    except TimeoutError as exc:
        raise HdhrError("Timed out waiting for the HDHomeRun device.") from exc

    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HdhrError("Device returned invalid JSON.") from exc


def _parse_tags(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, list):
        return tuple(str(item).strip() for item in raw if str(item).strip())
    text = str(raw).strip()
    if not text:
        return ()
    return tuple(part.strip() for part in text.split(",") if part.strip())


def _parse_lineup(payload: object) -> List[HdhrChannel]:
    if isinstance(payload, dict):
        items = payload.get("Channels", payload.get("channels", []))
    elif isinstance(payload, list):
        items = payload
    else:
        raise HdhrError("Unexpected lineup.json format.")

    if not isinstance(items, list):
        raise HdhrError("Unexpected lineup.json format.")

    channels: List[HdhrChannel] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("URL") or item.get("url") or "").strip()
        if not url:
            continue
        guide_number = str(item.get("GuideNumber") or item.get("guideNumber") or "").strip()
        guide_name = str(item.get("GuideName") or item.get("guideName") or "").strip()
        tags = _parse_tags(item.get("Tags") or item.get("tags"))
        channels.append(
            HdhrChannel(
                guide_number=guide_number,
                guide_name=guide_name,
                url=url,
                tags=tags,
            )
        )
    return channels


def resolve_lineup_url(base_url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Resolve lineup.json URL via discover.json, with a direct fallback."""
    base = normalize_device_url(base_url)
    discover_url = f"{base}/discover.json"
    try:
        data = _http_get_json(discover_url, timeout=timeout)
    except HdhrError:
        return f"{base}/lineup.json"

    if isinstance(data, dict):
        lineup = str(data.get("LineupURL") or data.get("lineupURL") or "").strip()
        if lineup:
            return lineup
    return f"{base}/lineup.json"


def fetch_lineup(
    user_url: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> List[HdhrChannel]:
    """Fetch and parse the HDHomeRun channel lineup for the given device URL."""
    text = (user_url or "").strip()
    if "://" not in text:
        text = "http://" + text
    parsed = urlparse(text)
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/lineup.json"):
        lineup_url = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    else:
        lineup_url = resolve_lineup_url(user_url, timeout=timeout)

    payload = _http_get_json(lineup_url, timeout=timeout)
    channels = _parse_lineup(payload)
    if not channels:
        raise HdhrError("No channels found in the device lineup.")
    return channels
