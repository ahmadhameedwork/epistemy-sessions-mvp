import pytest

from app.models import Session
from app.services.pipeline import Pipeline


def test_processing_checkpoint_recovers_after_transient_model_failure(demo, monkeypatch):
    client, factory, fake, checkpoint = demo
    with factory.begin() as db:
        lesson = Session(tutor_id=1, student_id=2, title="Recover me", transcript="Equations", status="processing")
        db.add(lesson)
        db.flush()
        session_id = lesson.id
    original = fake.with_structured_output
    calls = 0

    def fail_once(schema, include_raw=False):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Temporary model outage")
        return original(schema, include_raw)

    monkeypatch.setattr(fake, "with_structured_output", fail_once)
    pipeline = client.app.state.pipeline
    pipeline.run(session_id)
    with factory() as db:
        assert "RuntimeError" in db.get(Session, session_id).processing_error
    pipeline.close()
    client.app.state.pipeline = Pipeline(checkpoint, lambda: fake)
    client.app.state.pipeline.run(session_id, recover=True)
    with factory() as db:
        lesson = db.get(Session, session_id)
        assert lesson.status == "draft" and lesson.processing_error is None
    assert sum("Identify the subject" in prompt for prompt in fake.prompts) == 1


def test_failed_publish_can_retry_without_regeneration(demo, monkeypatch):
    client, factory, fake, _ = demo
    with factory.begin() as db:
        lesson = Session(tutor_id=1, student_id=2, title="Publish retry", transcript="Equations", status="processing")
        db.add(lesson)
        db.flush()
        session_id = lesson.id
    pipeline = client.app.state.pipeline
    pipeline.run(session_id)
    original = pipeline.publish
    attempts = 0

    def fail_once(state):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("Database unavailable")
        return original(state)

    # The graph captures a bound method at construction; replace its callable for this test.
    from app.agent.graph import build_graph
    pipeline.graph = build_graph(pipeline.checkpointer, fail_once, lambda: fake)
    with pytest.raises(RuntimeError, match="Database unavailable"):
        pipeline.share(session_id)
    with factory.begin() as db:
        db.get(Session, session_id).output.summary = "Edited after the publishing failure"
        db.get(Session, session_id).output.edited = True
    calls = fake.quiz_calls
    token = pipeline.share(session_id)
    assert token and fake.quiz_calls == calls and attempts == 2
    with factory() as db:
        assert db.get(Session, session_id).status == "shared"
        assert db.get(Session, session_id).output.summary == "Edited after the publishing failure"
