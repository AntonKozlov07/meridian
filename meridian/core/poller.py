"""Polls the source every few seconds and pushes state to the UI.

The UI interpolates the position between pushes, so 5s polling is enough.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from meridian.core.source import PlayerSource
from meridian.core.state import PlayerState

log = logging.getLogger(__name__)


class Poller:
    def __init__(self, source: PlayerSource, push: Callable[[PlayerState], None], interval: float = 5.0,
                 on_error: Callable[[Exception, int], None] | None = None):
        self._on_error = on_error
        self._source = source
        self._push = push
        self._interval = interval
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="meridian-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def poke(self, delay: float = 0.0) -> None:
        """Refresh soon, e.g. after a user action. Spotify needs a moment to reflect changes."""
        if delay:
            threading.Timer(delay, self._wake.set).start()
        else:
            self._wake.set()

    def _run(self) -> None:
        failures = 0
        while not self._stop.is_set():
            wait = self._interval
            try:
                self._push(self._source.poll())
                failures = 0
            except Exception as e:  # keep the loop alive; the UI keeps its last state
                failures += 1
                log.warning("poll failed (%d in a row): %s", failures, e)
                if self._on_error:
                    self._on_error(e, failures)
                wait = retry_after(e) or self._interval * 2
            self._wake.wait(wait)
            self._wake.clear()


def retry_after(exc: Exception) -> float | None:
    """Seconds to wait when Spotify answers 429."""
    if getattr(exc, "http_status", None) != 429:
        return None
    headers = getattr(exc, "headers", None) or {}
    try:
        return float(headers.get("Retry-After", 5)) + 1
    except (TypeError, ValueError):
        return 6.0
