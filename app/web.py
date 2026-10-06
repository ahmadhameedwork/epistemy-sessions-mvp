from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.config import ROOT
from app.db import SessionLocal
from app.models import User

templates = Jinja2Templates(directory=str(ROOT / "app/templates"))


def current_user(request: Request, role: str | None = None) -> User:
    with SessionLocal() as db:
        user = (
            db.get(User, request.session.get("user_id"))
            if request.session.get("user_id")
            else None
        )
    if user is None:
        raise HTTPException(303, headers={"Location": "/login"})
    if role and user.role != role:
        raise HTTPException(403, "This page belongs to the other demo role.")
    return user
