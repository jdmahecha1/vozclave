"""Turn microphone audio into utterances (recognized text + the audio that produced it)."""

from __future__ import annotations

import json
import queue
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

BLOCK_SIZE = 4000  # 0.25 s at 16 kHz
MAX_UTTERANCE_SECONDS = 6


@dataclass(frozen=True)
class Utterance:
    text: str
    audio: np.ndarray  # int16 mono PCM
    sample_rate: int


class Recognizer(Protocol):
    """The part of vosk.KaldiRecognizer we use (lets tests plug in a fake)."""

    def AcceptWaveform(self, data: bytes) -> bool: ...  # noqa: N802
    def Result(self) -> str: ...  # noqa: N802


def utterances(
    recognizer: Recognizer, blocks: Iterable[bytes], sample_rate: int = 16000
) -> Iterator[Utterance]:
    """Feed raw 16-bit PCM blocks to the recognizer and yield each finished utterance.

    The audio since the previous utterance is kept so the speaker can be verified on
    exactly the words that were recognized. It is capped to avoid growing forever
    while the room is silent.
    """
    buffer: list[bytes] = []
    max_bytes = MAX_UTTERANCE_SECONDS * sample_rate * 2
    size = 0
    for block in blocks:
        buffer.append(block)
        size += len(block)
        while size > max_bytes and len(buffer) > 1:
            size -= len(buffer.pop(0))
        if recognizer.AcceptWaveform(block):
            text = json.loads(recognizer.Result()).get("text", "")
            audio = np.frombuffer(b"".join(buffer), dtype=np.int16)
            buffer, size = [], 0
            if text:
                yield Utterance(text, audio, sample_rate)


def load_model(model_dir: Path):
    import vosk

    vosk.SetLogLevel(-1)
    if not model_dir.exists():
        raise FileNotFoundError(
            f"speech model not found at {model_dir} (run `vozclave download-model`)"
        )
    return vosk.Model(str(model_dir))


def make_recognizer(model, grammar: list[str], sample_rate: int = 16000):
    import vosk

    return vosk.KaldiRecognizer(model, sample_rate, json.dumps(grammar, ensure_ascii=False))


def unknown_words(model, words: Iterable[str]) -> list[str]:
    """Words the model can't recognize (they would silently never match)."""
    return sorted(w for w in words if model.vosk_model_find_word(w) < 0)


def microphone_blocks(sample_rate: int = 16000, device: int | str | None = None) -> Iterator[bytes]:
    import sounddevice as sd

    q: queue.Queue[bytes] = queue.Queue()

    def callback(indata, frames, time, status):  # runs on the audio thread
        q.put(bytes(indata))

    with sd.RawInputStream(
        samplerate=sample_rate,
        blocksize=BLOCK_SIZE,
        dtype="int16",
        channels=1,
        device=device,
        callback=callback,
    ):
        while True:
            yield q.get()
