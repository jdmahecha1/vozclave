import numpy as np

from vozclave.engine import Engine, Outcome
from vozclave.listener import Utterance
from vozclave.matcher import Matcher
from vozclave.speaker import SpeakerVerifier

AUDIO = np.zeros(1600, dtype=np.int16)


def utt(text):
    return Utterance(text, AUDIO, 16000)


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_engine(commands, verifier=None, cooldown=3.0):
    ran, clock = [], FakeClock()
    engine = Engine(Matcher(commands), ran.append, verifier, cooldown, clock)
    return engine, ran, clock


def verifier_with_score(score):
    # voiceprint = [1, 0]; the fake embedder returns a vector whose cosine with it is `score`
    vec = np.array([score, np.sqrt(1 - score**2)])
    return SpeakerVerifier(lambda audio, sr: vec, np.array([1.0, 0.0]), threshold=0.4)


def test_runs_matching_command(commands):
    engine, ran, _ = make_engine(commands)
    decision = engine.handle(utt("pon música"))
    assert decision.outcome is Outcome.EXECUTED
    assert [c.name for c in ran] == ["music"]


def test_ignores_speech_that_is_not_a_command(commands):
    engine, ran, _ = make_engine(commands)
    assert engine.handle(utt("[unk]")).outcome is Outcome.NO_MATCH
    assert ran == []


def test_cooldown_prevents_double_trigger(commands):
    engine, ran, clock = make_engine(commands, cooldown=3)
    engine.handle(utt("pon música"))
    clock.now += 1
    assert engine.handle(utt("abre spotify")).outcome is Outcome.COOLDOWN
    clock.now += 3
    assert engine.handle(utt("abre spotify")).outcome is Outcome.EXECUTED
    assert len(ran) == 2


def test_cooldown_is_per_command(commands):
    engine, ran, _ = make_engine(commands)
    engine.handle(utt("pon música"))
    assert engine.handle(utt("cierra spotify")).outcome is Outcome.EXECUTED


def test_rejects_other_voices(commands):
    engine, ran, _ = make_engine(commands, verifier_with_score(0.2))
    decision = engine.handle(utt("pon música"))
    assert decision.outcome is Outcome.WRONG_SPEAKER
    assert round(decision.score, 2) == 0.2
    assert ran == []


def test_accepts_owner_voice(commands):
    engine, ran, _ = make_engine(commands, verifier_with_score(0.7))
    decision = engine.handle(utt("pon música"))
    assert decision.outcome is Outcome.EXECUTED
    assert round(decision.score, 2) == 0.7


def test_rejected_attempt_does_not_start_cooldown(commands):
    engine, ran, _ = make_engine(commands, verifier_with_score(0.2))
    engine.handle(utt("pon música"))
    engine._verifier = verifier_with_score(0.9)
    assert engine.handle(utt("pon música")).outcome is Outcome.EXECUTED
