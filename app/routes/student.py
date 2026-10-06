from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.models import Session
from app.web import current_user, templates

router = APIRouter(prefix="/student")


@router.get("")
def vault(request: Request):
    student = current_user(request, "student")
    with SessionLocal() as db:
        lessons = db.scalars(
            select(Session)
            .where(Session.student_id == student.id, Session.status == "shared")
            .options(joinedload(Session.tutor))
            .order_by(Session.created_at.desc())
        ).all()
    return templates.TemplateResponse(
        request=request,
        name="student.html",
        context={"student": student, "lessons": lessons},
    )


@router.get("/sessions/{session_id}")
def session_detail(request: Request, session_id: int):
    student = current_user(request, "student")
    with SessionLocal() as db:
        lesson = db.scalar(
            select(Session)
            .where(
                Session.id == session_id,
                Session.student_id == student.id,
                Session.status == "shared",
            )
            .options(
                joinedload(Session.output),
                joinedload(Session.tutor),
                joinedload(Session.student),
            )
        )
        if lesson is None or lesson.output is None:
            raise HTTPException(404, "Shared session not found.")
        return templates.TemplateResponse(
            request=request,
            name="shared_session.html",
            context={"lesson": lesson, "public": False},
        )
