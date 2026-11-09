import hashlib
import json
import logging
import pickle
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T")

_FINGERPRINT_CHUNK = 2 * 1024 * 1024


class StageCache:
    """Pickle cache for expensive pipeline stages, keyed by video content + the config that shaped the result."""

    def __init__(self, cache_dir: Path, enabled: bool = True):
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def fingerprint_video(path: Path) -> str:
        digest = hashlib.sha1()
        size = path.stat().st_size
        digest.update(str(size).encode())
        with path.open("rb") as fh:
            digest.update(fh.read(_FINGERPRINT_CHUNK))
            fh.seek(max(0, size - _FINGERPRINT_CHUNK))
            digest.update(fh.read(_FINGERPRINT_CHUNK))
        return digest.hexdigest()[:16]

    @staticmethod
    def make_key(*parts: Any) -> str:
        normalized = [p.model_dump(mode="json") if isinstance(p, BaseModel) else p for p in parts]
        payload = json.dumps(normalized, sort_keys=True, default=str)
        return hashlib.sha1(payload.encode()).hexdigest()[:16]

    def _path(self, stage: str, key: str) -> Path:
        return self.cache_dir / f"{stage}_{key}.pkl"

    def load(self, stage: str, key: str) -> Any | None:
        path = self._path(stage, key)
        if not (self.enabled and path.exists()):
            return None
        try:
            with path.open("rb") as fh:
                return pickle.load(fh)
        except (pickle.UnpicklingError, EOFError, AttributeError, ModuleNotFoundError) as exc:
            logger.warning("Ignoring unreadable cache entry %s (%s)", path.name, exc)
            return None

    def save(self, stage: str, key: str, value: Any) -> None:
        if not self.enabled:
            return
        tmp = self._path(stage, key).with_suffix(".tmp")
        with tmp.open("wb") as fh:
            pickle.dump(value, fh, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(self._path(stage, key))

    def get_or_compute(self, stage: str, key: str, compute: Callable[[], T]) -> T:
        cached = self.load(stage, key)
        if cached is not None:
            logger.info("Cache hit for stage '%s'", stage)
            return cached
        value = compute()
        self.save(stage, key, value)
        return value
