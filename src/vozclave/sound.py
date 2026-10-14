"""Play the confirmation sound without blocking the listener."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class Sound:
    def __init__(self, file: Path | None, volume: float):
        self._data = None
        self._rate = 0
        if file is None or volume == 0:
            return
        try:
            import soundfile as sf

            data, self._rate = sf.read(str(file), dtype="float32")
            self._data = data * volume
        except Exception as e:  # a broken sound file should never stop the commands
            log.warning("could not load sound %s: %s", file, e)

    def play(self) -> None:
        if self._data is None:
            return
        import sounddevice as sd

        sd.play(self._data, self._rate)
