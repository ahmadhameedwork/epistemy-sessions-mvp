from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import transcription


def test_explicit_fallback_and_invalid_selection(monkeypatch):
    monkeypatch.setattr(settings, "use_fallback_transcripts", True)
    assert "Distribution" not in transcription.transcribe_session(None, "1")
    assert "parentheses" in transcription.transcribe_session(None, "2")
    with pytest.raises(ValueError, match="matching sample"):
        transcription.transcribe_session(None, "../../elsewhere")


def test_whisper_call_and_selected_fallback(tmp_path, monkeypatch):
    recording = tmp_path / "sample.mp4"
    recording.write_bytes(b"mock recording")
    monkeypatch.setattr(settings, "use_fallback_transcripts", False)
    monkeypatch.setattr(settings, "openai_api_key", "test-not-a-real-key")
    calls = []

    def create(**kwargs):
        calls.append((kwargs["model"], kwargs["file"].read()))
        return SimpleNamespace(text=" Actual transcript. ")

    client = SimpleNamespace(
        audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create))
    )
    monkeypatch.setattr(transcription, "OpenAI", lambda **kwargs: client)
    assert (
        transcription.transcribe_session(str(recording), None) == "Actual transcript."
    )
    assert calls == [("whisper-1", b"mock recording")]

    def fail(**kwargs):
        raise RuntimeError("API unavailable")

    client.audio.transcriptions.create = fail
    assert "fractions" in transcription.transcribe_session(str(recording), "3")
    with pytest.raises(ValueError, match="Transcription failed"):
        transcription.transcribe_session(str(recording), None)
