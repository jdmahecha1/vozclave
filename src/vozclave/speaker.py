"""Speaker verification: is this utterance from the enrolled user?

Each utterance is turned into a 192-number "voice embedding" with SpeechBrain's ECAPA-TDNN
model (trained on thousands of speakers from VoxCeleb). Embeddings of the same person point
in a similar direction, so cosine similarity tells us how alike two voices are.
The voiceprint is just the average embedding of the enrollment samples.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

Embedder = Callable[[np.ndarray, int], np.ndarray]
MODEL_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"


def _unit(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    if norm == 0:
        raise ValueError("cannot normalize a zero vector")
    return v / norm


def ecapa_embedder(cache_dir: Path) -> Embedder:
    """Load the ECAPA model once and return a function audio -> embedding.

    Imported lazily because torch is heavy and optional (`pip install vozclave[voiceid]`).
    """
    try:
        import torch
        import torchaudio.functional as F
        from speechbrain.inference.speaker import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy
    except ImportError as e:
        raise RuntimeError(
            'voice verification needs extra packages: pip install "vozclave[voiceid]"'
        ) from e

    # SpeechBrain sets its loggers to INFO on import; keep the console readable
    for name in list(logging.root.manager.loggerDict):
        if name.startswith("speechbrain"):
            logging.getLogger(name).setLevel(logging.WARNING)

    model = EncoderClassifier.from_hparams(
        source=MODEL_SOURCE,
        savedir=str(cache_dir / "ecapa"),
        run_opts={"device": "cpu"},
        local_strategy=LocalStrategy.COPY,  # symlinks need admin rights on Windows
    )

    def embed(audio: np.ndarray, sample_rate: int) -> np.ndarray:
        x = torch.from_numpy(to_float(audio))
        if sample_rate != 16000:
            x = F.resample(x, sample_rate, 16000)
        with torch.no_grad():
            return model.encode_batch(x.unsqueeze(0)).squeeze().numpy()

    return embed


def to_float(audio: np.ndarray) -> np.ndarray:
    """int16 PCM -> float32 in [-1, 1]; float input is passed through (mono)."""
    audio = np.asarray(audio)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if audio.dtype == np.int16:
        return audio.astype(np.float32) / 32768.0
    return audio.astype(np.float32)


class SpeakerVerifier:
    def __init__(self, embed: Embedder, voiceprint: np.ndarray, threshold: float):
        self._embed = embed
        self.voiceprint = _unit(np.asarray(voiceprint, dtype=np.float32))
        self.threshold = threshold

    def similarity(self, audio: np.ndarray, sample_rate: int) -> float:
        return float(_unit(self._embed(audio, sample_rate)) @ self.voiceprint)

    def is_owner(self, audio: np.ndarray, sample_rate: int) -> tuple[bool, float]:
        score = self.similarity(audio, sample_rate)
        return score >= self.threshold, score


def build_voiceprint(
    embed: Embedder, samples: Sequence[np.ndarray], sample_rate: int
) -> tuple[np.ndarray, list[float]]:
    """Average the samples into a voiceprint.

    Also returns, for each sample, how similar it is to the average of the *others*
    (leave-one-out). Low values flag a bad recording (noise, someone else talking...).
    """
    if len(samples) < 3:
        raise ValueError("at least 3 samples are needed to build a reliable voiceprint")
    embeddings = np.array([_unit(embed(s, sample_rate)) for s in samples])
    voiceprint = _unit(embeddings.mean(axis=0))
    consistency = []
    for i in range(len(embeddings)):
        rest = _unit(np.delete(embeddings, i, axis=0).mean(axis=0))
        consistency.append(float(embeddings[i] @ rest))
    return voiceprint, consistency


def save_voiceprint(path: Path, voiceprint: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, voiceprint.astype(np.float32))


def load_voiceprint(path: Path) -> np.ndarray | None:
    return np.load(path) if path.exists() else None
