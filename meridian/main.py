"""Starts the native window, wires the API and pushes state into the page."""
from __future__ import annotations

import json
import logging

import webview

from meridian import config
from meridian.api import Api


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    api = Api(config.load())
    window = webview.create_window(
        "Meridian",
        url=str(config.UI_DIR / "index.html"),
        js_api=api,
        width=1440,
        height=900,
        min_size=(800, 600),
    )

    def push(state: dict) -> None:
        window.evaluate_js(f"window.meridian && window.meridian.update({json.dumps(state)})")

    api._attach(push)
    webview.start()


if __name__ == "__main__":
    main()
