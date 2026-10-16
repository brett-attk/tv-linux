"""HDHomeRun HTTP discover / lineup helpers."""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.client import HTTPException
from typing import List, NoReturn, Optional, Sequence
from urllib.parse import urlparse, urlunparse

from .logging_setup import get_logger

log = get_logger(__name__)

DEFAULT_TIMEOUT = 8.0
MAX_RESPONSE_BYTES = 2_000_000


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

    def __init__(
        self,
        message: str,
        *,
        connectivity: bool = False,
        url: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.connectivity = connectivity
        self.url = url


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

    base = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    return base.rstrip("/")


def _raise_connectivity(message: str, url: str, cause: BaseException) -> NoReturn:
    log.error("%s (%s)", message, url, exc_info=cause)
    raise HdhrError(message, connectivity=True, url=url) from cause


def _http_get_json(url: str, timeout: float) -> object:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "tv-app/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # HTTPError is also a URLError subclass; handle status codes first.
        detail = f"HTTP {exc.code} from HDHomeRun while fetching {url}"
        log.error("%s", detail, exc_info=exc)
        if exc.code == 404:
            raise HdhrError(
                "HDHomeRun endpoint not found (404). Check the device address.",
                url=url,
            ) from exc
        if exc.code >= 500:
            raise HdhrError(
                f"HDHomeRun reported a server error (HTTP {exc.code}). "
                "The device may be busy or scanning channels.",
                url=url,
            ) from exc
        raise HdhrError(f"HDHomeRun returned HTTP {exc.code}.", url=url) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.gaierror):
            _raise_connectivity(
                "Could not resolve the HDHomeRun hostname. Check the address and DNS.",
                url,
                exc,
            )
        if isinstance(reason, ConnectionRefusedError):
            _raise_connectivity(
                "Connection refused by the HDHomeRun. Is the device powered on?",
                url,
                exc,
            )
        if isinstance(reason, (TimeoutError, socket.timeout)):
            _raise_connectivity(
                "Timed out waiting for the HDHomeRun. Check network connectivity.",
                url,
                exc,
            )
        if isinstance(reason, ssl.SSLError):
            _raise_connectivity(
                "TLS/SSL error talking to the HDHomeRun.",
                url,
                exc,
            )
        _raise_connectivity(
            f"Could not reach the HDHomeRun device: {reason}",
            url,
            exc,
        )
    except (TimeoutError, socket.timeout) as exc:
        _raise_connectivity(
            "Timed out waiting for the HDHomeRun. Check network connectivity.",
            url,
            exc,
        )
    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as exc:
        _raise_connectivity(
            "Connection to the HDHomeRun was interrupted.",
            url,
            exc,
        )
    except (HTTPException, OSError) as exc:
        _raise_connectivity(
            f"Network error talking to the HDHomeRun: {exc}",
            url,
            exc,
        )

    if len(body) > MAX_RESPONSE_BYTES:
        log.error("Response from %s exceeded %s bytes", url, MAX_RESPONSE_BYTES)
        raise HdhrError("HDHomeRun response was too large to process.", url=url)
    if not body or not body.strip():
        log.error("Empty response from %s", url)
        raise HdhrError("HDHomeRun returned an empty response.", url=url)

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        log.error("Invalid UTF-8 from %s", url, exc_info=exc)
        raise HdhrError("HDHomeRun returned a non-text response.", url=url) from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.error("Invalid JSON from %s: %s", url, exc, exc_info=exc)
        raise HdhrError("HDHomeRun returned invalid JSON.", url=url) from exc


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
        # Some firmwares wrap channels; others return a bare list.
        if payload.get("ScanInProgress") in (1, True, "1"):
            log.warning("HDHomeRun reports a channel scan is in progress")
            raise HdhrError(
                "HDHomeRun is scanning channels. Try again when the scan finishes."
            )
        items = payload.get("Channels", payload.get("channels", []))
    elif isinstance(payload, list):
        items = payload
    else:
        log.error("Unexpected lineup payload type: %s", type(payload).__name__)
        raise HdhrError("Unexpected lineup.json format from the HDHomeRun.")

    if not isinstance(items, list):
        log.error("Lineup Channels field is not a list: %r", type(items).__name__)
        raise HdhrError("Unexpected lineup.json format from the HDHomeRun.")

    channels: List[HdhrChannel] = []
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        url = str(item.get("URL") or item.get("url") or "").strip()
        if not url:
            skipped += 1
            continue
        guide_number = str(
            item.get("GuideNumber") or item.get("guideNumber") or ""
        ).strip()
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
    if skipped:
        log.info("Skipped %s lineup entries without usable URLs", skipped)
    return channels


def resolve_lineup_url(base_url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Resolve lineup.json URL via discover.json, with a direct fallback."""
    base = normalize_device_url(base_url)
    discover_url = f"{base}/discover.json"
    try:
        data = _http_get_json(discover_url, timeout=timeout)
    except HdhrError as exc:
        if exc.connectivity:
            # Same host will fail the same way for lineup.json.
            raise
        log.warning(
            "discover.json unavailable for %s (%s); falling back to lineup.json",
            base,
            exc,
        )
        return f"{base}/lineup.json"

    if isinstance(data, dict):
        lineup = str(data.get("LineupURL") or data.get("lineupURL") or "").strip()
        if lineup:
            log.info("Resolved lineup URL via discover.json: %s", lineup)
            return lineup
        log.warning("discover.json missing LineupURL for %s", base)
    else:
        log.warning("discover.json was not an object for %s", base)
    return f"{base}/lineup.json"


def fetch_lineup(
    user_url: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> List[HdhrChannel]:
    """Fetch and parse the HDHomeRun channel lineup for the given device URL."""
    log.info("Fetching HDHomeRun lineup for %r", user_url)
    try:
        text = (user_url or "").strip()
        if "://" not in text:
            text = "http://" + text
        parsed = urlparse(text)
        path = (parsed.path or "").rstrip("/")
        if path.endswith("/lineup.json"):
            if not parsed.scheme or not parsed.netloc:
                raise HdhrError("Enter a valid http:// URL or IP address.")
            lineup_url = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
        else:
            lineup_url = resolve_lineup_url(user_url, timeout=timeout)

        payload = _http_get_json(lineup_url, timeout=timeout)
        channels = _parse_lineup(payload)
        if not channels:
            log.error("Lineup at %s contained no usable channels", lineup_url)
            raise HdhrError(
                "No channels found in the HDHomeRun lineup. "
                "Confirm a channel scan has been completed on the device.",
                url=lineup_url,
            )
        log.info("Fetched %s channel(s) from %s", len(channels), lineup_url)
        return channels
    except HdhrError:
        raise
    except Exception as exc:
        log.exception("Unexpected failure fetching lineup for %r", user_url)
        raise HdhrError(
            f"Unexpected error talking to the HDHomeRun: {exc}"
        ) from exc
