import pytest

from meridian.sources.spotify import source


@pytest.fixture(autouse=True)
def _no_verify_delay(monkeypatch):
    """The play-verification step sleeps and re-reads playback; switch it off unless a test asks for it."""
    monkeypatch.setattr(source, "VERIFY_PLAYBACK", False)
    monkeypatch.setattr(source, "VERIFY_DELAY_S", 0)
