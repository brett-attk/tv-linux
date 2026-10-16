"""Helpers for channel-store writes that may raise OSError."""

from __future__ import annotations

from typing import Callable, Optional, Tuple, TypeVar

T = TypeVar("T")


def try_store_write(action: Callable[[], T]) -> Tuple[Optional[T], Optional[OSError]]:
    """Run a store mutation.

    Returns ``(result, None)`` on success, or ``(None, error)`` when the
    underlying filesystem write fails.
    """
    try:
        return action(), None
    except OSError as exc:
        return None, exc
