"""Load and validate the TOML config file."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from vozclave import paths

ACTIONS = ("open", "close", "run")
DEFAULT_SOUND = "default"


class ConfigError(ValueError):
    """The config file is missing something or has an invalid value."""


@dataclass(frozen=True)
class Command:
    name: str
    phrases: tuple[str, ...]
    action: str
    target: str


@dataclass(frozen=True)
class VoiceConfig:
    enabled: bool = True
    threshold: float = 0.40


@dataclass(frozen=True)
class SoundConfig:
    file: Path | None = None
    volume: float = 0.3


@dataclass(frozen=True)
class Config:
    model: Path
    commands: tuple[Command, ...]
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    sound: SoundConfig = field(default_factory=SoundConfig)
    cooldown_seconds: float = 3.0
    input_device: int | str | None = None
    sample_rate: int = 16000


def _number(table: dict, key: str, default: float, lo: float, hi: float, where: str) -> float:
    value = table.get(key, default)
    if not isinstance(value, int | float) or isinstance(value, bool) or not lo <= value <= hi:
        raise ConfigError(f"{where}.{key} must be a number between {lo} and {hi}, got {value!r}")
    return float(value)


def _parse_command(raw: dict, index: int) -> Command:
    where = f"commands[{index}]"
    name = raw.get("name") or f"command {index + 1}"

    phrases = raw.get("phrases")
    if isinstance(phrases, str):
        phrases = [phrases]
    if not phrases or not all(isinstance(p, str) and p.strip() for p in phrases):
        raise ConfigError(f"{where} ({name}) needs at least one non-empty phrase")

    action = raw.get("action")
    if action not in ACTIONS:
        raise ConfigError(f"{where} ({name}): action must be one of {ACTIONS}, got {action!r}")

    target = raw.get("target")
    if not isinstance(target, str) or not target.strip():
        raise ConfigError(f"{where} ({name}) needs a 'target'")

    return Command(name, tuple(p.strip() for p in phrases), action, target.strip())


def _resolve_sound(value: str, base: Path) -> Path | None:
    if not value:
        return None
    if value == DEFAULT_SOUND:
        return Path(__file__).parent / "assets" / "activate.wav"
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def _resolve_model(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    if (base / path).exists():
        return base / path
    return paths.models_dir() / path


def parse(data: dict, base: Path) -> Config:
    """Build a Config from an already-parsed TOML dict. Relative paths resolve against `base`."""
    commands = data.get("commands")
    if not commands:
        raise ConfigError("the config needs at least one [[commands]] entry")
    parsed = tuple(_parse_command(c, i) for i, c in enumerate(commands))

    voice = data.get("voice", {})
    sound = data.get("sound", {})
    device = data.get("input_device")
    if device is not None and not isinstance(device, int | str):
        raise ConfigError("input_device must be a device number or name")

    return Config(
        model=_resolve_model(data.get("model", "vosk-model-small-es-0.42"), base),
        commands=parsed,
        voice=VoiceConfig(
            enabled=bool(voice.get("enabled", True)),
            threshold=_number(voice, "threshold", 0.40, 0.0, 1.0, "voice"),
        ),
        sound=SoundConfig(
            file=_resolve_sound(sound.get("file", DEFAULT_SOUND), base),
            volume=_number(sound, "volume", 0.3, 0.0, 1.0, "sound"),
        ),
        cooldown_seconds=_number(data, "cooldown_seconds", 3.0, 0.0, 3600.0, "config"),
        input_device=device,
    )


def load(path: Path) -> Config:
    if not path.exists():
        raise ConfigError(f"config file not found: {path} (run `vozclave init` to create one)")
    with path.open("rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"{path} is not valid TOML: {e}") from e
    return parse(data, path.parent)
