"""Downloads the football-specific models.

    uv run python scripts/download_models.py

- Ball and pitch models: open-source roboflow/sports project (MIT licence).
- Player detector: RF-DETR fine-tuned on SoccerNet (julianzu9612/RFDETR-Soccernet on Hugging Face, ~1.5 GB;
  SoccerNet data is research-licensed - check before commercial use).

YOLO26 weights (yolo26n-pose.pt, yolo26s.pt) are downloaded automatically by Ultralytics on first use.
"""

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.app_config import get_app_config  # noqa: E402

# Google Drive ids published in https://github.com/roboflow/sports/blob/main/examples/soccer/setup.sh
MODELS = {
    "football-ball-detection.pt": "1isw4wx-MK9h9LMr36VvIWlJD6ppUvw7V",
    "football-pitch-detection.pt": "1Ma5Kt86tgpdjCTKfum79YMgNnSjcoOyf",
}
SAMPLE_VIDEOS = {
    "0bfacc_0.mp4": "12TqauVZ9tLAv8kWxTTBFWtgt2hNQ4_ZF",
    "121364_0.mp4": "1vVwjW1dE1drIdd4ZSILfbCGPD4weoNiu",
    "2e57b9_0.mp4": "19PGw55V8aA6GZu5-Aac5_9mCy3fNxmEf",
    "08fd33_0.mp4": "1OG8K6wqUw9t7lp9ms1M48DxRhwTYciK-",
    "573e61_0.mp4": "1yYPKuXbHsCxqjA9G-S6aeR2Kcnos8RPU",
}
RFDETR_URL = "https://huggingface.co/julianzu9612/RFDETR-Soccernet/resolve/main/weights/checkpoint_best_regular.pth"
_MIN_VALID_BYTES = 100_000


def download(drive_id: str, destination: Path) -> None:
    fetch(f"https://drive.usercontent.google.com/download?id={drive_id}&export=download&confirm=t", destination)


def fetch(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > _MIN_VALID_BYTES:
        print(f"  already present: {destination.name}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {destination.name} ...")
    urllib.request.urlretrieve(url, destination)
    if destination.stat().st_size < _MIN_VALID_BYTES:
        destination.unlink()
        raise RuntimeError(f"Download of {destination.name} failed (the server returned an error page)")


def main() -> None:
    config = get_app_config()
    models_dir = config.resolve(config.paths.models_dir)
    print("Models:")
    for name, drive_id in MODELS.items():
        download(drive_id, models_dir / name)
    if config.detector.type == "rfdetr":
        fetch(RFDETR_URL, models_dir / config.detector.checkpoint)
    if "--samples" in sys.argv:
        print("Sample clips (DFL Bundesliga):")
        for name, drive_id in SAMPLE_VIDEOS.items():
            download(drive_id, models_dir.parent / "samples" / name)


if __name__ == "__main__":
    main()
