import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.schemas.video import JobProgress

logger = logging.getLogger(__name__)

# One worker: the GPU (4 GB) can only hold one tracking/rendering job at a time. Jobs queue in submit order.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis-worker")


def submit(job: Callable[[], None], name: str) -> None:
    def run() -> None:
        try:
            job()
        except Exception:  # noqa: BLE001 - last-resort guard so one failed job never kills the worker
            logger.exception("Background job %s crashed", name)

    _executor.submit(run)


class StageProgress:
    """Maps pipeline stage events onto an overall 0-100% bar and persists them (throttled)."""

    def __init__(self, stages: dict[str, tuple[float, float, str]], persist: Callable[[JobProgress], None]):
        self.stages = stages
        self.persist = persist
        self._last_percent = -1.0
        self._last_stage = ""
        self._last_write = 0.0

    def __call__(self, stage: str, fraction: float) -> None:
        if stage not in self.stages:
            return
        start, end, message = self.stages[stage]
        percent = round(start + (end - start) * fraction, 1)
        now = time.monotonic()
        if stage == self._last_stage and (percent - self._last_percent < 1.0 or now - self._last_write < 1.0):
            return
        self._last_stage, self._last_percent, self._last_write = stage, percent, now
        self.persist(JobProgress(stage=stage, percent=percent, message=message))
