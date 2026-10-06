from typing import TypedDict


class SessionState(TypedDict, total=False):
    session_id: int
    video_path: str | None
    fallback_id: str | None
    transcript: str
    previous_transcript: str | None
    topics: dict | None
    progress: dict | None
    quiz: list[dict] | None
    retries: int
    error: str | None
    validation_errors: list[str]
    quiz_valid: bool
    approved: bool
    edited: bool
    share_token: str | None


def initial_state(
    session_id: int,
    transcript: str = "",
    previous_transcript: str | None = None,
    video_path: str | None = None,
    fallback_id: str | None = None,
) -> SessionState:
    return SessionState(
        session_id=session_id,
        video_path=video_path,
        fallback_id=fallback_id,
        transcript=transcript,
        previous_transcript=previous_transcript,
        topics=None,
        progress=None,
        quiz=None,
        retries=0,
        error=None,
        validation_errors=[],
        quiz_valid=False,
        approved=False,
        edited=False,
        share_token=None,
    )
