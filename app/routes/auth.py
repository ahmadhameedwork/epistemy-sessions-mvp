from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.web import templates

router = APIRouter()


@router.get("/")
def home(request: Request):
    return RedirectResponse("/login", status_code=303)


@router.get("/login")
def login_form(request: Request):
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.id)).all()
    return templates.TemplateResponse(
        request=request, name="login.html", context={"users": users}
    )


@router.post("/login")
def login(request: Request, user_id: int = Form()):
    with SessionLocal() as db:
        user = db.get(User, user_id)
    if user is None:
        raise HTTPException(400, "Choose a seeded user. Run python seed.py if needed.")
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse(f"/{user.role}", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
