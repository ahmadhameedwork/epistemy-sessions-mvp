import secrets
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.config import ROOT, settings
from app.db import SessionLocal
from app.models import Session, User
from app.schemas import EditedOutput
from app.services.pipeline import output_dict, store_output
from app.services.transcription import MAX_UPLOAD_BYTES, SAMPLES, SUPPORTED_FORMATS
from app.web import current_user, templates

router = APIRouter(prefix="/tutor")


def tutor_session(db, session_id: int, tutor_id: int) -> Session:
    lesson = db.scalar(select(Session).where(Session.id == session_id, Session.tutor_id == tutor_id)
                       .options(joinedload(Session.output), joinedload(Session.student), joinedload(Session.tutor)))
    if lesson is None:
        raise HTTPException(404, "Session not found.")
    return lesson


def panel(request: Request, lesson: Session, errors: list[str] | None = None,
          content: dict | None = None, status_code: int = 200, partial: bool = False):
    return templates.TemplateResponse(
        request=request, name="tutor_panel.html" if partial else "tutor_session.html",
        context={"lesson": lesson, "content": content or (output_dict(lesson.output) if lesson.output else None),
                 "errors": errors or [], "share_url": str(request.base_url) + f"share/{lesson.share_token}" if lesson.share_token else None},
        status_code=status_code,
    )


@router.get("")
def dashboard(request: Request):
    tutor = current_user(request, "tutor")
    with SessionLocal() as db:
        lessons = db.scalars(select(Session).where(Session.tutor_id == tutor.id)
                             .options(joinedload(Session.student)).order_by(Session.created_at.desc())).all()
        students = db.scalars(select(User).where(User.role == "student")).all()
    return templates.TemplateResponse(request=request, name="tutor.html", context={
        "tutor": tutor, "lessons": lessons, "students": students, "samples": SAMPLES,
        "fallback_mode": settings.use_fallback_transcripts,
    })


async def save_recording(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(400, "Upload mp4, mp3, mpeg, mpga, m4a, wav, or webm.")
    folder = ROOT / "data/uploads"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{secrets.token_hex(16)}{suffix}"
    size = 0
    try:
        with target.open("wb") as recording:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(400, "Recordings must be smaller than 25 MB for this prototype.")
                recording.write(chunk)
        if size == 0:
            raise HTTPException(400, "The uploaded recording is empty.")
        return str(target)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


@router.post("/sessions")
async def create_session(request: Request, background_tasks: BackgroundTasks,
                         title: str = Form(), student_id: int = Form(),
                         previous_session_id: str = Form(""), fallback_id: str = Form(""),
                         video: UploadFile | None = None):
    tutor = current_user(request, "tutor")
    title = title.strip()
    if not title or len(title) > 200:
        raise HTTPException(400, "Enter a session title of 1 to 200 characters.")
    if fallback_id and fallback_id not in SAMPLES:
        raise HTTPException(400, "Unknown sample transcript.")
    if settings.use_fallback_transcripts and not fallback_id:
        raise HTTPException(400, "Select a sample transcript in fallback mode.")
    if not settings.use_fallback_transcripts and (video is None or not video.filename):
        raise HTTPException(400, "Upload a recording for live transcription.")
    try:
        previous_id = int(previous_session_id) if previous_session_id else None
    except ValueError:
        raise HTTPException(400, "Choose a valid previous session.")
    with SessionLocal() as db:
        student = db.get(User, student_id)
        if student is None or student.role != "student":
            raise HTTPException(400, "Choose a student.")
        if previous_id:
            previous = db.get(Session, previous_id)
            if previous is None or previous.tutor_id != tutor.id or previous.student_id != student_id or not previous.transcript.strip():
                raise HTTPException(400, "The previous session must belong to this tutor and student and have a transcript.")
    video_path = await save_recording(video) if video and video.filename else None
    try:
        with SessionLocal.begin() as db:
            lesson = Session(tutor_id=tutor.id, student_id=student_id, title=title,
                             video_path=video_path, previous_session_id=previous_id, status="processing")
            db.add(lesson)
            db.flush()
            session_id = lesson.id
    except Exception:
        if video_path:
            Path(video_path).unlink(missing_ok=True)
        raise
    background_tasks.add_task(request.app.state.pipeline.run, session_id, fallback_id or None)
    return RedirectResponse(f"/tutor/sessions/{session_id}", status_code=303)


@router.get("/sessions/{session_id}")
def session_detail(request: Request, session_id: int, poll: bool = False):
    tutor = current_user(request, "tutor")
    with SessionLocal() as db:
        lesson = tutor_session(db, session_id, tutor.id)
        return panel(request, lesson, partial=poll)


def parse_edit(form) -> dict:
    questions = []
    fields = ["q_id", "q_question", "q_type", "q_options", "q_answer", "q_explanation", "q_difficulty"]
    columns = [form.getlist(field) for field in fields]
    if len({len(column) for column in columns}) != 1:
        raise ValueError("Every quiz question needs all its fields.")
    for values in zip(*columns):
        qid, question, kind, options, answer, explanation, difficulty = values
        questions.append(dict(id=qid, question=question, type=kind,
                              options=[item.strip() for item in options.splitlines() if item.strip()] or None,
                              answer=answer, explanation=explanation, difficulty=difficulty))
    return dict(subject=form.get("subject", ""), summary=form.get("summary", ""),
                progress_feedback=form.get("progress_feedback", ""), quiz=questions,
                **{field: [item.strip() for item in form.get(field, "").splitlines() if item.strip()]
                   for field in ["subtopics", "strengths", "areas_to_improve"]})


@router.post("/sessions/{session_id}/save")
async def save(request: Request, session_id: int):
    tutor = current_user(request, "tutor")
    form = await request.form()
    with request.app.state.pipeline.lock(session_id):
        with SessionLocal.begin() as db:
            lesson = tutor_session(db, session_id, tutor.id)
            if lesson.output is None or lesson.status == "processing":
                raise HTTPException(400, "Wait for a draft before editing.")
            content = None
            try:
                content = parse_edit(form)
                validated = EditedOutput.model_validate(content).model_dump()
            except (ValidationError, ValueError) as exc:
                return panel(request, lesson, errors=[str(exc)], content=content, status_code=422)
            store_output(db, lesson, validated, edited=True)
    return RedirectResponse(f"/tutor/sessions/{session_id}", status_code=303)


@router.post("/sessions/{session_id}/share")
def share(request: Request, session_id: int):
    tutor = current_user(request, "tutor")
    with SessionLocal() as db:
        tutor_session(db, session_id, tutor.id)
    try:
        request.app.state.pipeline.share(session_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "Publishing failed. Your edits are saved; retry after checking server logs.") from exc
    return RedirectResponse(f"/tutor/sessions/{session_id}", status_code=303)


@router.post("/sessions/{session_id}/paid")
def toggle_paid(request: Request, session_id: int):
    tutor = current_user(request, "tutor")
    with request.app.state.pipeline.lock(session_id):
        with SessionLocal.begin() as db:
            lesson = tutor_session(db, session_id, tutor.id)
            lesson.paid = not lesson.paid
    return RedirectResponse(f"/tutor/sessions/{session_id}", status_code=303)


@router.post("/settings/calendly")
def save_calendly(request: Request, calendly_url: str = Form("")):
    tutor = current_user(request, "tutor")
    value = calendly_url.strip()
    parsed = urlparse(value)
    if value and (parsed.scheme != "https" or parsed.hostname != "calendly.com" or parsed.username or parsed.password or parsed.port):
        raise HTTPException(400, "Enter an https://calendly.com/... booking URL, or leave it blank to remove the button.")
    if len(value) > 500:
        raise HTTPException(400, "The Calendly URL is too long.")
    with SessionLocal.begin() as db:
        db.get(User, tutor.id).calendly_url = value or None
    return RedirectResponse("/tutor", status_code=303)
