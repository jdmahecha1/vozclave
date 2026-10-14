import json

import numpy as np

from vozclave import listener


class FakeRecognizer:
    """Finishes an utterance on the blocks listed in `finals`, with the given texts."""

    def __init__(self, finals):
        self.finals = dict(finals)
        self.count = 0
        self.text = ""

    def AcceptWaveform(self, data):  # noqa: N802
        self.count += 1
        if self.count in self.finals:
            self.text = self.finals[self.count]
            return True
        return False

    def Result(self):  # noqa: N802
        return json.dumps({"text": self.text})


def block(value, n=4):
    return np.full(n, value, dtype=np.int16).tobytes()


def test_yields_text_with_the_audio_that_produced_it():
    rec = FakeRecognizer({2: "pon música", 3: "cierra spotify"})
    out = list(listener.utterances(rec, [block(1), block(2), block(3)]))
    assert [u.text for u in out] == ["pon música", "cierra spotify"]
    assert out[0].audio.tolist() == [1] * 4 + [2] * 4
    assert out[1].audio.tolist() == [3] * 4


def test_empty_results_are_skipped():
    rec = FakeRecognizer({1: "", 2: "abre spotify"})
    out = list(listener.utterances(rec, [block(1), block(2)]))
    assert [u.text for u in out] == ["abre spotify"]
    assert out[0].audio.tolist() == [2] * 4  # the silence before was discarded


def test_buffer_is_capped_during_long_silence(monkeypatch):
    monkeypatch.setattr(listener, "MAX_UTTERANCE_SECONDS", 1)
    rec = FakeRecognizer({100: "pon música"})
    blocks = [block(i, n=4000) for i in range(100)]  # 100 x 0.25 s
    (utt,) = listener.utterances(rec, blocks, sample_rate=16000)
    assert len(utt.audio) <= 16000
    assert utt.audio[-1] == 99


class FakeModel:
    def vosk_model_find_word(self, word):
        return -1 if word in {"jarvisito", "zzz"} else 1


def test_unknown_words():
    assert listener.unknown_words(FakeModel(), {"abre", "zzz", "jarvisito"}) == ["jarvisito", "zzz"]
