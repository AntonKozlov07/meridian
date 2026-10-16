import importlib
import json
import sys

from meridian import config, main as main_mod
from meridian.api import Api
from meridian.config import Config
from meridian.settings import Settings
from meridian.sources.spotify.source import SpotifySource


def test_settings_roundtrip_and_validation(tmp_path):
    f = tmp_path / "settings.json"
    s = Settings(f)
    assert s.get_all() == {"theme": None, "covers": None}
    assert s.set("theme", "light") and not s.set("theme", "purple") and not s.set("volume", 1)
    assert Settings(f).get_all() == {"theme": "light", "covers": None}
    assert s.set("theme", None) and Settings(f).get_all() == {"theme": None, "covers": None}


def test_settings_ignore_a_corrupt_or_hostile_file(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text("{not json", encoding="utf-8")
    assert Settings(f).get_all() == {"theme": None, "covers": None}
    f.write_text(json.dumps({"theme": "<script>", "other": 1}), encoding="utf-8")
    assert Settings(f).get_all() == {"theme": None, "covers": None}


def test_api_settings(tmp_path):
    api = Api(Config()); api._settings = Settings(tmp_path / "s.json")
    assert api.set_setting("theme", "dark")["ok"] and api.get_settings()["theme"] == "dark"
    assert api.set_setting("theme", "nope")["ok"] is False


def test_packaged_app_keeps_its_env_in_the_user_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    try:
        c = importlib.reload(config)
        assert c.FROZEN and c.UI_DIR == tmp_path / "bundle" / "meridian" / "ui"
        assert c.ENV_PATH == tmp_path / ".meridian" / ".env"
        c.save_env_value("SPOTIFY_CLIENT_ID", "x", c.ENV_PATH)  # creates the folder too
        assert c.ENV_PATH.read_text(encoding="utf-8") == "SPOTIFY_CLIENT_ID=x\n"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_selfcheck_passes_on_the_source_tree(monkeypatch, capsys):
    monkeypatch.setattr(main_mod, "MODULES", ("json", "httpx"))  # pywebview needs a GUI stack the test box may lack
    assert main_mod.selfcheck() == 0
    assert "OK" in capsys.readouterr().out


def test_selfcheck_reports_missing_files_and_modules(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "UI_DIR", tmp_path)
    monkeypatch.setattr(main_mod, "MODULES", ("json", "not_a_real_module"))
    assert main_mod.selfcheck() == 1
    out = capsys.readouterr().out
    assert "missing UI file: index.html" in out and "missing bundled fonts" in out and "not_a_real_module" in out


def test_fonts_are_bundled_and_no_stylesheet_calls_the_network():
    ui = config.UI_DIR
    css = (ui / "fonts.css").read_text(encoding="utf-8")
    for name in __import__("re").findall(r"url\(fonts/([^)]+)\)", css):
        assert (ui / "fonts" / name).stat().st_size > 1000, name
    for f in ui.glob("*.css"):
        assert "googleapis" not in f.read_text(encoding="utf-8") and "http" not in f.read_text(encoding="utf-8").replace("http://www.w3.org", ""), f.name
    assert not (ui / "fonts" / "OFL.txt").exists() or "404" not in (ui / "fonts" / "OFL.txt").read_text(encoding="utf-8")


def test_unavailable_current_track_is_flagged():
    from unittest.mock import MagicMock
    sp = MagicMock()
    item = {"id": "a", "uri": "u", "name": "n", "duration_ms": 1000, "is_playable": False, "artists": [], "album": {"name": "x"}}
    sp.current_playback.return_value = {"is_playing": True, "progress_ms": 0, "item": item, "device": {"id": "d"}}
    sp.devices.return_value = {"devices": []}
    sp.current_user.return_value = {"id": "u1", "display_name": "Anton Kozlov"}
    st = SpotifySource(sp).poll()
    assert st.track.is_playable is False and st.user_name == "Anton Kozlov"
    assert sp.current_playback.call_args.kwargs["market"] == "from_token"


def test_cover_choice_is_saved_and_validated(tmp_path):
    f = tmp_path / "settings.json"
    s = Settings(f)
    assert s.set("covers", "geo") and not s.set("covers", "neon")
    assert Settings(f).get_all()["covers"] == "geo"
    api = Api(Config()); api._settings = Settings(f)
    assert api.get_settings()["covers"] == "geo" and api.set_setting("covers", "real")["ok"]
