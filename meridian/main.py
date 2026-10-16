"""Starts the native window, wires the API and pushes state into the page."""
from __future__ import annotations

import importlib
import json
import logging
import sys

from meridian import __version__, config

UI_FILES = ("index.html", "app.js", "theme.js", "tokens.css", "components.css", "fonts.css", "live.css")
MODULES = ("webview", "spotipy", "httpx", "pylast", "keyring", "PIL", "colorthief", "dotenv")


def selfcheck() -> int:
    """Confirms the bundled files and libraries are all present, without opening a window.
    The packaged app is checked this way in CI: `Meridian.exe --selfcheck`."""
    problems = [f"missing UI file: {n}" for n in UI_FILES if not (config.UI_DIR / n).is_file()]
    if not list((config.UI_DIR / "fonts").glob("*.woff2")):
        problems.append("missing bundled fonts")
    for mod in MODULES:
        try:
            importlib.import_module(mod)
        except Exception as e:  # ImportError, or a GUI library failing to load
            problems.append(f"cannot import {mod}: {type(e).__name__}: {e}")
    print(f"Meridian {__version__}  ui={config.UI_DIR}  frozen={config.FROZEN}")
    print("OK" if not problems else "PROBLEMS:\n  " + "\n  ".join(problems))
    return 1 if problems else 0


def main() -> None:
    if "--version" in sys.argv:
        print(__version__)
        return
    if "--selfcheck" in sys.argv:
        raise SystemExit(selfcheck())

    import webview  # imported here so --selfcheck can report a missing GUI library instead of crashing

    from meridian.api import Api

    config.DATA_DIR.mkdir(exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(config.DATA_DIR / "meridian.log", encoding="utf-8")]
    if sys.stderr:  # the packaged app has no console
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers)

    api = Api(config.load())
    window = webview.create_window(
        "Meridian",
        url=str(config.UI_DIR / "index.html"),
        js_api=api,
        width=1440,
        height=900,
        min_size=(800, 600),
        background_color="#131210",  # no white flash while the page loads
    )

    def push(state: dict) -> None:
        try:
            window.evaluate_js(f"window.meridian && window.meridian.update({json.dumps(state)})")
        except Exception as e:  # window closing or page still loading: the next poll will resend
            logging.getLogger(__name__).debug("push skipped: %s", e)

    def push_enrich(e: dict) -> None:
        try:
            window.evaluate_js(f"window.meridian && window.meridian.enrich({json.dumps(e)})")
        except Exception as ex:
            logging.getLogger(__name__).debug("enrich push skipped: %s", ex)

    api._attach(push, push_enrich)
    window.events.closing += api._shutdown
    webview.start()


if __name__ == "__main__":
    main()
