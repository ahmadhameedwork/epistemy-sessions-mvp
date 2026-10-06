import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, make_engine
from app.main import app
from app.services.pipeline import Pipeline
from tests.fakes import FakeModel


@pytest.fixture
def demo(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    for name in ["app.db", "app.web", "app.routes.auth", "app.routes.tutor", "app.routes.student", "app.routes.share", "app.services.pipeline", "seed"]:
        module = importlib.import_module(name)
        monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setattr(importlib.import_module("app.db"), "engine", engine)
    monkeypatch.setattr(settings, "use_fallback_transcripts", True)
    monkeypatch.setattr(settings, "langsmith_tracing", False)
    monkeypatch.setattr(importlib.import_module("app.routes.tutor"), "ROOT", tmp_path)
    fake = FakeModel(invalid_attempts=1)
    checkpoint = str(tmp_path / "checkpoints.db")
    monkeypatch.setattr(importlib.import_module("app.main"), "Pipeline", lambda: Pipeline(checkpoint, lambda: fake))
    importlib.import_module("seed").seed()
    with TestClient(app) as client:
        yield client, factory, fake, checkpoint
    engine.dispose()
