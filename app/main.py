from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import ROOT, settings
from app.db import init_db
from app.routes import auth, share, student, tutor
from app.services.pipeline import Pipeline
from app.web import templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.pipeline = Pipeline()
    try:
        yield
    finally:
        app.state.pipeline.close()


app = FastAPI(title="Epistemy Sessions", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory=str(ROOT / "app/static")), name="static")
app.include_router(auth.router)
app.include_router(tutor.router)
app.include_router(student.router)
app.include_router(share.router)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if exc.status_code == 303 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(exc.headers["Location"], status_code=303)
    return templates.TemplateResponse(request=request, name="error.html",
                                      context={"message": exc.detail, "status": exc.status_code},
                                      status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    return templates.TemplateResponse(request=request, name="error.html",
                                      context={"message": "Check the form fields and choose valid values.", "status": 422},
                                      status_code=422)


@app.get("/health")
def health():
    return {"status": "ok"}
