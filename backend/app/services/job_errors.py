"""User-facing messages for failed background jobs (the full exception is logged, never shown)."""

_FRIENDLY = (
    (("out of memory", "outofmemory", "cuda error", "cublas", "cudnn"),
     "The video needed more processing memory than is available. Try a shorter or lower-resolution clip."),
    (("cannot open", "could not open", "no frames", "moov atom", "invalid data"),
     "The video file could not be read. Re-export it as MP4 (H.264) and upload it again."),
    (("not enough to separate teams", "reliably coloured players"),
     "Not enough players were visible to tell the two teams apart. Use a wide broadcast or tactical camera clip."),
    (("checkpoint not found", "no such file", "download_models"),
     "A required analysis component is missing on the server. Ask an administrator to install the models."),
)
_DEFAULT = "Processing failed unexpectedly. Try again; if it keeps failing, try a different clip."


def public_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    for needles, message in _FRIENDLY:
        if any(needle in text for needle in needles):
            return message
    return _DEFAULT
