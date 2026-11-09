import hashlib
import logging
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import imageio_ffmpeg
from google import genai
from google.genai import errors, types

from app.core.app_config import GeminiConfig
from app.engine.cache.stage_cache import StageCache
from app.engine.gemini.prompts import GeminiTargetContext, build_prompt
from app.engine.gemini.schemas import GeminiMatchAnalysis

logger = logging.getLogger(__name__)
# Agentic responses legitimately contain the model's own tool-call parts; the SDK warns about them on every read.
logging.getLogger("google_genai.types").setLevel(logging.ERROR)


class GeminiAgenticAnalyst:
    """Counts match events with Gemini's agentic video understanding and returns a structured event log.

    In agentic mode Gemini receives only a pointer to the video and decides itself which segments to
    watch, at what frame rate and through which modality, instead of uniformly sampling the whole file.
    Falls back to standard sampled video understanding if the model or SDK rejects agentic processing.
    """

    def __init__(self, config: GeminiConfig, api_key: str, cache: StageCache):
        self.config = config
        self.cache = cache
        self.client = genai.Client(api_key=api_key)

    def analyze(
        self, video_path: Path, fingerprint: str, context: GeminiTargetContext, max_seconds: float | None
    ) -> tuple[GeminiMatchAnalysis | None, str]:
        key = self._cache_key(fingerprint, context, max_seconds)
        cached = self.cache.load("gemini", key)
        if cached is not None:
            analysis, mode = cached
            return analysis, f"ok ({mode}, cached)"

        try:
            upload_path = self._clip(video_path, max_seconds)
            video_file = self._upload(upload_path)
            analysis, mode = self._generate(video_file, context)
        except (errors.APIError, TimeoutError, RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
            logger.error("Gemini analysis failed: %s", exc)
            return None, f"failed: {exc}"[:200]

        self.cache.save("gemini", key, (analysis, mode))
        return analysis, f"ok ({mode})"

    def _generate(self, video_file: types.File, context: GeminiTargetContext) -> tuple[GeminiMatchAnalysis, str]:
        if self.config.agentic:
            try:
                return self._call(video_file, context, agentic=True), "agentic"
            except errors.ClientError as exc:
                logger.warning("Agentic video processing rejected (%s); falling back to sampled video", exc)
        return self._call(video_file, context, agentic=False), "sampled video"

    def _call(self, video_file: types.File, context: GeminiTargetContext, agentic: bool) -> GeminiMatchAnalysis:
        video_part = types.Part(
            file_data=types.FileData(file_uri=video_file.uri, mime_type=video_file.mime_type),
            media_processing=types.MediaProcessing.AGENTIC if agentic else types.MediaProcessing.STATIC,
            video_metadata=None if agentic else types.VideoMetadata(fps=self.config.fallback_fps),
        )
        parts = [video_part]
        if context.reference_image_jpeg:
            parts.append(types.Part.from_text(text="Reference crop of the TARGET PLAYER from this video:"))
            parts.append(types.Part.from_bytes(data=context.reference_image_jpeg, mime_type="image/jpeg"))
        parts.append(types.Part.from_text(text=build_prompt(context)))

        config = types.GenerateContentConfig(
            temperature=self.config.temperature,
            response_mime_type="application/json",
            response_schema=GeminiMatchAnalysis,
        )
        response = self.client.models.generate_content(
            model=self.config.model,
            contents=[types.Content(role="user", parts=parts)],
            config=config,
        )
        if response.parsed is not None:
            return response.parsed
        if not response.text:
            raise RuntimeError("Gemini returned an empty response")
        return GeminiMatchAnalysis.model_validate_json(response.text)

    def _upload(self, path: Path) -> types.File:
        logger.info("Uploading %s to Gemini Files API", path.name)
        video_file = self.client.files.upload(file=str(path))
        waited = 0.0
        while video_file.state and video_file.state.name == "PROCESSING":
            if waited >= self.config.file_poll_timeout_s:
                raise TimeoutError("Gemini file processing timed out")
            time.sleep(self.config.file_poll_interval_s)
            waited += self.config.file_poll_interval_s
            video_file = self.client.files.get(name=video_file.name)
        if video_file.state and video_file.state.name == "FAILED":
            raise RuntimeError("Gemini failed to process the uploaded video")
        return video_file

    def _clip(self, video_path: Path, max_seconds: float | None) -> Path:
        """Trims the video to the analysed duration so Gemini's timestamps line up with the tracking data."""
        if max_seconds is None:
            return video_path
        clip = self.cache.cache_dir / f"{video_path.stem}_first{int(max_seconds)}s.mp4"
        if not clip.exists():
            subprocess.run(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(video_path),
                 "-t", str(max_seconds), "-c", "copy", str(clip)],
                check=True,
            )
        return clip

    def _cache_key(self, fingerprint: str, context: GeminiTargetContext, max_seconds: float | None) -> str:
        image_hash = hashlib.sha1(context.reference_image_jpeg).hexdigest() if context.reference_image_jpeg else None
        return StageCache.make_key(
            fingerprint, self.config, replace(context, reference_image_jpeg=None).__dict__, image_hash, max_seconds
        )
