from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import ROOT, settings
from app.db import init_db
from app.routes import auth, student, tutor
from app.services.pipeline import Pipeline


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


@app.get("/health")
def health():
    return {"status": "ok"}
