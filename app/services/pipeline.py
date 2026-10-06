import logging
import secrets
import sqlite3
import threading
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.agent.graph import build_graph
from app.agent.model import configure_tracing
from app.agent.nodes import output_from_state
from app.agent.state import initial_state
from app.config import settings
from app.db import SessionLocal
from app.models import Session, SessionOutput
from app.schemas import EditedOutput

logger = logging.getLogger(__name__)


def output_dict(output: SessionOutput) -> dict:
    return {field: getattr(output, field) for field in EditedOutput.model_fields}


def store_output(db, lesson: Session, content: dict, edited: bool) -> None:
    if lesson.output is None:
        lesson.output = SessionOutput(session_id=lesson.id, **content, edited=edited)
        db.add(lesson.output)
    else:
        for field, value in content.items():
            setattr(lesson.output, field, value)
        lesson.output.edited = edited


class Pipeline:
    """Own one persistent graph and serialize mutations to each session thread."""

    def __init__(self, path: str | None = None, model_factory=None):
        configure_tracing()
        checkpoint_path = Path(path or settings.checkpoint_db_path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(checkpoint_path), check_same_thread=False, timeout=10)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.checkpointer = SqliteSaver(self.connection)
        self.checkpointer.setup()
        self.graph = build_graph(self.checkpointer, self.publish, model_factory)
        self._locks: dict[int, threading.RLock] = {}
        self._guard = threading.Lock()

    def close(self) -> None:
        self.connection.close()

    def lock(self, session_id: int) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(session_id, threading.RLock())

    def config(self, session_id: int) -> dict:
        return {"configurable": {"thread_id": f"session-{session_id}"},
                "run_name": f"session-{session_id}", "tags": ["epistemy"],
                "metadata": {"session_id": session_id}, "recursion_limit": 30}

    def run(self, session_id: int, fallback_id: str | None = None, recover: bool = False) -> None:
        with self.lock(session_id):
            try:
                config = self.config(session_id)
                with SessionLocal() as db:
                    lesson = db.get(Session, session_id)
                    if lesson is None or lesson.status != "processing":
                        return
                    previous = db.get(Session, lesson.previous_session_id) if lesson.previous_session_id else None
                    state = initial_state(lesson.id, lesson.transcript, previous.transcript if previous else None,
                                          lesson.video_path, fallback_id)
                snapshot = self.graph.get_state(config)
                if snapshot.values:
                    if not recover:
                        return
                    result = self.graph.invoke(None, config, durability="sync") if snapshot.next else snapshot.values
                else:
                    result = self.graph.invoke(state, config, durability="sync")
                self.materialize(session_id, result)
            except Exception as exc:
                logger.exception("Session %s generation failed", session_id)
                message = str(exc) if isinstance(exc, ValueError) else f"Generation failed ({type(exc).__name__}). Check API configuration and server logs, then recover or upload again."
                self.record_error(session_id, message)

    def materialize(self, session_id: int, state: dict) -> None:
        with SessionLocal.begin() as db:
            lesson = db.get(Session, session_id)
            if lesson is None or lesson.status == "shared":
                return
            lesson.transcript = state.get("transcript", lesson.transcript)
            if state.get("error"):
                lesson.processing_error = state["error"][:2000]
                return
            snapshot = self.graph.get_state(self.config(session_id))
            if any(task.interrupts for task in snapshot.tasks):
                content = EditedOutput.model_validate(output_from_state(state)).model_dump()
                store_output(db, lesson, content, edited=False)
                lesson.status = "draft"
                lesson.processing_error = None

    def record_error(self, session_id: int, message: str) -> None:
        with SessionLocal.begin() as db:
            lesson = db.get(Session, session_id)
            if lesson is not None and lesson.status == "processing":
                lesson.processing_error = message[:2000]

    def share(self, session_id: int) -> str:
        with self.lock(session_id):
            with SessionLocal() as db:
                lesson = db.get(Session, session_id)
                if lesson.status == "shared":
                    return lesson.share_token
                if lesson.status != "draft" or lesson.output is None:
                    raise ValueError("Wait for a valid draft before sharing.")
                content = EditedOutput.model_validate(output_dict(lesson.output)).model_dump()
                edited = lesson.output.edited
            snapshot = self.graph.get_state(self.config(session_id))
            if not any(task.interrupts for task in snapshot.tasks):
                raise ValueError("This session has no pending tutor review.")
            self.graph.invoke(Command(resume={"approved": True, "output": content, "edited": edited}),
                              self.config(session_id), durability="sync")
            with SessionLocal() as db:
                return db.get(Session, session_id).share_token

    def publish(self, state: dict) -> dict:
        if not state.get("approved"):
            raise ValueError("Tutor approval is required.")
        content = EditedOutput.model_validate(output_from_state(state)).model_dump()
        with SessionLocal.begin() as db:
            lesson = db.get(Session, state["session_id"])
            if lesson.status == "shared":
                return {"share_token": lesson.share_token}
            store_output(db, lesson, content, edited=state.get("edited", False))
            lesson.share_token = lesson.share_token or secrets.token_urlsafe(24)
            lesson.status = "shared"
            lesson.processing_error = None
            token = lesson.share_token
        return {"share_token": token}
