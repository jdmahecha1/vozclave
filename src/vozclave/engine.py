"""Decide what to do with each utterance: ignore it, reject the speaker, or run a command."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from vozclave.config import Command
from vozclave.listener import Utterance
from vozclave.matcher import Matcher
from vozclave.speaker import SpeakerVerifier


class Outcome(Enum):
    NO_MATCH = "no_match"
    COOLDOWN = "cooldown"
    WRONG_SPEAKER = "wrong_speaker"
    EXECUTED = "executed"


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    command: Command | None = None
    score: float | None = None


class Engine:
    def __init__(
        self,
        matcher: Matcher,
        on_command: Callable[[Command], None],
        verifier: SpeakerVerifier | None = None,
        cooldown_seconds: float = 3.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._matcher = matcher
        self._on_command = on_command
        self._verifier = verifier
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._last_run: dict[str, float] = {}

    def handle(self, utterance: Utterance) -> Decision:
        command = self._matcher.match(utterance.text)
        if command is None:
            return Decision(Outcome.NO_MATCH)

        last = self._last_run.get(command.name)
        if last is not None and self._clock() - last < self._cooldown:
            return Decision(Outcome.COOLDOWN, command)

        score = None
        if self._verifier is not None:
            ok, score = self._verifier.is_owner(utterance.audio, utterance.sample_rate)
            if not ok:
                return Decision(Outcome.WRONG_SPEAKER, command, score)

        self._last_run[command.name] = self._clock()
        self._on_command(command)
        return Decision(Outcome.EXECUTED, command, score)
