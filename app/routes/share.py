from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.models import Session
from app.web import templates

router = APIRouter(prefix="/share")


@router.get("/{token}", name="public_session")
def public_session(request: Request, token: str):
    with SessionLocal() as db:
        lesson = db.scalar(select(Session).where(Session.share_token == token, Session.status == "shared")
                           .options(joinedload(Session.output), joinedload(Session.tutor), joinedload(Session.student)))
        if lesson is None or lesson.output is None:
            raise HTTPException(404, "Share link not found.")
        return templates.TemplateResponse(request=request, name="shared_session.html", context={"lesson": lesson, "public": True})
