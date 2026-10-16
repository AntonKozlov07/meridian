import pytest

from meridian.enrich import lyrics
from meridian.sources.spotify import source


@pytest.fixture(autouse=True)
def _fast_and_quiet(monkeypatch):
    """Switch off the sleeps and the play-verification step unless a test asks for them."""
    monkeypatch.setattr(source, "VERIFY_PLAYBACK", False)
    monkeypatch.setattr(source, "VERIFY_DELAY_S", 0)
    monkeypatch.setattr(source, "QUEUE_SETTLE_S", 0)
    monkeypatch.setattr(lyrics, "MIN_INTERVAL", 0)
    monkeypatch.setattr(lyrics, "RETRY_DELAY", 0)
