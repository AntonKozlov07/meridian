"""Small user preferences kept in ~/.meridian/settings.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from meridian import config

log = logging.getLogger(__name__)

ALLOWED = {"theme": {"dark", "light", None}}  # None means follow the system


class Settings:
    def __init__(self, path: Path | None = None):
        self._path = path or config.DATA_DIR / "settings.json"
        self._data: dict = {}
        try:
            loaded = json.loads(self._path.read_text())
            if isinstance(loaded, dict):
                self._data = {k: v for k, v in loaded.items() if k in ALLOWED and v in ALLOWED[k]}
        except (OSError, ValueError):
            pass  # first run, or an unreadable file: start from defaults

    def get_all(self) -> dict:
        return {k: self._data.get(k) for k in ALLOWED}

    def set(self, key: str, value) -> bool:
        if key not in ALLOWED or value not in ALLOWED[key]:
            return False
        self._data[key] = value
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data))
        except OSError as e:
            log.warning("could not save settings: %s", e)
        return True
