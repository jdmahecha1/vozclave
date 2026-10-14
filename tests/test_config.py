import pytest

from vozclave import config
from vozclave.config import ConfigError

VALID = {
    "commands": [
        {"name": "music", "phrases": ["pon música"], "action": "open", "target": "spotify:"}
    ]
}


def test_example_config_is_valid():
    cfg = config.load(config.Path(config.__file__).parent / "example_config.toml")
    assert len(cfg.commands) == 4
    assert cfg.voice.enabled
    assert cfg.sound.file.name == "activate.wav"
    assert cfg.sound.file.exists()


def test_defaults(tmp_path, isolated_home):
    cfg = config.parse(VALID, tmp_path)
    assert cfg.voice.threshold == 0.40
    assert cfg.cooldown_seconds == 3.0
    assert cfg.model == isolated_home / "models" / "vosk-model-small-es-0.42"


def test_single_phrase_string_is_accepted(tmp_path):
    data = {"commands": [{"phrases": "abre spotify", "action": "open", "target": "spotify:"}]}
    assert config.parse(data, tmp_path).commands[0].phrases == ("abre spotify",)


def test_relative_sound_is_resolved_from_config_folder(tmp_path):
    data = {**VALID, "sound": {"file": "sounds/beep.wav"}}
    assert config.parse(data, tmp_path).sound.file == tmp_path / "sounds" / "beep.wav"


def test_empty_sound_means_silence(tmp_path):
    assert config.parse({**VALID, "sound": {"file": ""}}, tmp_path).sound.file is None


@pytest.mark.parametrize(
    "command, message",
    [
        ({"phrases": [], "action": "open", "target": "x"}, "phrase"),
        ({"phrases": ["  "], "action": "open", "target": "x"}, "phrase"),
        ({"phrases": ["hola"], "action": "delete", "target": "x"}, "action"),
        ({"phrases": ["hola"], "action": "open"}, "target"),
    ],
)
def test_invalid_commands(tmp_path, command, message):
    with pytest.raises(ConfigError, match=message):
        config.parse({"commands": [command]}, tmp_path)


def test_needs_commands(tmp_path):
    with pytest.raises(ConfigError, match="at least one"):
        config.parse({}, tmp_path)


@pytest.mark.parametrize("value", [-0.1, 1.5, "high", True])
def test_threshold_must_be_between_0_and_1(tmp_path, value):
    with pytest.raises(ConfigError, match="threshold"):
        config.parse({**VALID, "voice": {"threshold": value}}, tmp_path)


def test_missing_file_has_helpful_message(tmp_path):
    with pytest.raises(ConfigError, match="vozclave init"):
        config.load(tmp_path / "nope.toml")


def test_invalid_toml(tmp_path):
    bad = tmp_path / "config.toml"
    bad.write_text("commands = [", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid TOML"):
        config.load(bad)
