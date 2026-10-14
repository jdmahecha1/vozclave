"""Map recognized text to the command it belongs to."""

from __future__ import annotations

import unicodedata

from vozclave.config import Command

UNKNOWN = "[unk]"


def normalize(text: str) -> str:
    """Lowercase, drop accents and collapse spaces: 'Ábre  Spotify' -> 'abre spotify'."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    no_accents = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return " ".join(no_accents.split())


class Matcher:
    def __init__(self, commands: tuple[Command, ...] | list[Command]):
        self._by_phrase: dict[str, Command] = {}
        for command in commands:
            for phrase in command.phrases:
                key = normalize(phrase)
                other = self._by_phrase.get(key)
                if other is not None and other is not command:
                    raise ValueError(
                        f"phrase {phrase!r} is used by both {other.name!r} and {command.name!r}"
                    )
                self._by_phrase[key] = command
        self._phrases = [p for c in commands for p in c.phrases]

    def grammar(self) -> list[str]:
        """Phrases the recognizer is allowed to output. `[unk]` absorbs everything else,
        so random speech becomes "unknown" instead of being forced into a command."""
        return [p.lower() for p in self._phrases] + [UNKNOWN]

    def match(self, text: str) -> Command | None:
        if not text or UNKNOWN in text:
            return None
        return self._by_phrase.get(normalize(text))

    def words(self) -> set[str]:
        return {w for p in self._phrases for w in p.lower().split()}
