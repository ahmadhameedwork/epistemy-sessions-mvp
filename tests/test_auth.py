from sqlalchemy import select

from app.config import settings
from app.models import Session, User


def test_login_redirects_and_seed_is_idempotent(demo):
    client, factory, _, _ = demo
    import seed

    seed.seed()
    with factory() as db:
        assert len(db.scalars(select(User)).all()) == 2
        assert len(db.scalars(select(Session)).all()) == 3
    response = client.get("/tutor", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/login"
    assert client.post("/login", data={"user_id": 999}).status_code == 400
    for user_id, destination in [(1, "/tutor"), (2, "/student")]:
        response = client.post(
            "/login", data={"user_id": user_id}, follow_redirects=False
        )
        assert (
            response.status_code == 303 and response.headers["location"] == destination
        )
    client.get("/logout")
    assert client.get("/student", follow_redirects=False).status_code == 303


def test_missing_llm_key_produces_visible_failure(demo, monkeypatch):
    client, factory, _, _ = demo
    from app.agent.model import build_model

    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    # Rebuild with the real provider factory, so this verifies the actual credential path.
    from app.agent.graph import build_graph

    pipeline = client.app.state.pipeline
    pipeline.graph = build_graph(pipeline.checkpointer, pipeline.publish, build_model)
    client.post("/login", data={"user_id": 1})
    response = client.post(
        "/tutor/sessions",
        data={"title": "No credentials", "student_id": 2, "fallback_id": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get(response.headers["location"])
    assert "Set OPENAI_API_KEY" in page.text and "hx-trigger" not in page.text
    with factory() as db:
        lesson = db.scalar(select(Session).where(Session.title == "No credentials"))
        assert (
            lesson.status == "processing"
            and lesson.output is None
            and not lesson.share_token
        )
