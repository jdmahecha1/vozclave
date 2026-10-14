"""Download the offline Vosk speech models."""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

BASE_URL = "https://alphacephei.com/vosk/models/"
MODELS = {
    "es": "vosk-model-small-es-0.42",
    "en": "vosk-model-small-en-us-0.15",
    "pt": "vosk-model-small-pt-0.3",
    "fr": "vosk-model-small-fr-0.22",
}


def download(lang: str, dest_dir: Path) -> Path:
    if lang not in MODELS:
        raise ValueError(f"unknown language {lang!r}, choose one of: {', '.join(MODELS)}")
    name = MODELS[lang]
    target = dest_dir / name
    if target.exists():
        return target

    dest_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"{name}.zip"
        print(f"Downloading {name} (~40 MB)...")
        urllib.request.urlretrieve(BASE_URL + f"{name}.zip", archive)
        with zipfile.ZipFile(archive) as z:
            for member in z.namelist():  # refuse paths that would escape the folder
                if Path(member).is_absolute() or ".." in Path(member).parts:
                    raise RuntimeError(f"unsafe path in archive: {member}")
            z.extractall(tmp)
        shutil.move(str(Path(tmp) / name), target)
    return target
