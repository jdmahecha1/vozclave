import numpy as np
import pytest

from vozclave import speaker


def embed_from_first_samples(audio, sample_rate):
    """Fake embedder: uses the first 3 samples of the audio as the 'embedding'."""
    return np.asarray(audio[:3], dtype=np.float32)


def test_voiceprint_is_unit_average():
    samples = [np.array([1, 0, 0]), np.array([0.9, 0.1, 0]), np.array([1, 0.1, 0])]
    vp, consistency = speaker.build_voiceprint(embed_from_first_samples, samples, 16000)
    assert np.isclose(np.linalg.norm(vp), 1)
    assert vp[0] > 0.9
    assert all(c > 0.9 for c in consistency)


def test_consistency_flags_the_odd_sample():
    samples = [np.array([1, 0, 0]), np.array([1, 0.05, 0]), np.array([0, 0, 1])]
    _, consistency = speaker.build_voiceprint(embed_from_first_samples, samples, 16000)
    assert consistency.index(min(consistency)) == 2


def test_needs_three_samples():
    with pytest.raises(ValueError, match="at least 3"):
        speaker.build_voiceprint(embed_from_first_samples, [np.ones(3)] * 2, 16000)


def test_verifier_threshold():
    v = speaker.SpeakerVerifier(embed_from_first_samples, np.array([1, 0, 0]), threshold=0.5)
    assert v.is_owner(np.array([2, 0.1, 0]), 16000)[0]
    ok, score = v.is_owner(np.array([0, 1, 0]), 16000)
    assert not ok and abs(score) < 1e-6


def test_save_and_load(tmp_path):
    path = tmp_path / "sub" / "vp.npy"
    assert speaker.load_voiceprint(path) is None
    speaker.save_voiceprint(path, np.array([0.6, 0.8]))
    assert np.allclose(speaker.load_voiceprint(path), [0.6, 0.8])


def test_to_float():
    pcm = np.array([0, 16384, -32768], dtype=np.int16)
    assert np.allclose(speaker.to_float(pcm), [0, 0.5, -1])
    stereo = np.array([[0.2, 0.4], [0.0, 1.0]], dtype=np.float32)
    assert np.allclose(speaker.to_float(stereo), [0.3, 0.5])
