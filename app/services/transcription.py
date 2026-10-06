import logging
from pathlib import Path

from openai import OpenAI

from app.config import ROOT, settings

logger = logging.getLogger(__name__)
SAMPLES = {"1": "Linear equations: baseline", "2": "Linear equations: progress", "3": "Fractions: baseline"}
MAX_UPLOAD_BYTES = 25_000_000
SUPPORTED_FORMATS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}


def load_fallback(sample_id: str | None) -> str:
    if sample_id not in SAMPLES:
        raise ValueError("Select a matching sample transcript for fallback mode.")
    path = ROOT / f"data/transcripts/session-{sample_id}.txt"
    if not path.is_file():
        raise ValueError("The selected fallback transcript is missing.")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("The selected fallback transcript is empty.")
    return text


def transcribe_session(video_path: str | None, fallback_id: str | None) -> str:
    if settings.use_fallback_transcripts:
        return load_fallback(fallback_id)
    try:
        if not video_path:
            raise ValueError("Upload a recording to use live transcription.")
        path = Path(video_path)
        if path.suffix.lower() not in SUPPORTED_FORMATS or path.stat().st_size > MAX_UPLOAD_BYTES:
            raise ValueError("Whisper needs a supported recording smaller than 25 MB.")
        if not settings.openai_api_key:
            raise ValueError("Set OPENAI_API_KEY to use Whisper.")
        with path.open("rb") as recording:
            result = OpenAI(api_key=settings.openai_api_key, timeout=60, max_retries=2).audio.transcriptions.create(
                model="whisper-1", file=recording,
            )
        if not result.text.strip():
            raise ValueError("Whisper returned an empty transcript.")
        return result.text.strip()
    except Exception as exc:
        if fallback_id in SAMPLES:
            logger.warning("Whisper failed (%s); using explicitly selected sample %s", type(exc).__name__, fallback_id)
            return load_fallback(fallback_id)
        raise ValueError(f"Transcription failed ({type(exc).__name__}). Select a matching fallback transcript or check the recording and API configuration.") from exc
