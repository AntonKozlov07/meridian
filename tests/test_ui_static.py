"""Guards the static UI against the design rules in CLAUDE.md."""
import re
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "meridian" / "ui"


def test_ui_files_exist():
    for name in ("index.html", "app.js", "tokens.css", "components.css"):
        assert (UI / name).exists(), name


def test_no_radius_above_16px():
    css = (UI / "components.css").read_text()
    for m in re.finditer(r"border-radius:\s*(\d+)px", css):
        assert int(m.group(1)) <= 16


def test_no_blue_or_purple_tokens():
    css = (UI / "tokens.css").read_text()
    for hexv in re.findall(r"#([0-9a-fA-F]{6})\b", css):
        r, g, b = (int(hexv[i:i + 2], 16) for i in (0, 2, 4))
        assert not (b > r + 20 and b > g + 20), hexv
