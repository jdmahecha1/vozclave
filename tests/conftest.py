import pytest

from vozclave.config import Command


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never touch the real user's config, models or voiceprint."""
    monkeypatch.setenv("VOZCLAVE_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture
def commands():
    return (
        Command("music", ("pon música", "abre spotify"), "open", "spotify:"),
        Command("close music", ("cierra spotify",), "close", "Spotify"),
    )
