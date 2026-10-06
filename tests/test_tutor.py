from sqlalchemy import select

from app.models import Session
from app.services.pipeline import Pipeline, output_dict


def edit_form(content):
    form = {
        field: content[field] for field in ["subject", "summary", "progress_feedback"]
    }
    for field in ["subtopics", "strengths", "areas_to_improve"]:
        form[field] = "\n".join(content[field])
    for field in [
        "id",
        "question",
        "type",
        "options",
        "answer",
        "explanation",
        "difficulty",
    ]:
        form[f"q_{field}"] = [
            "\n".join(q[field] or []) if field == "options" else str(q[field])
            for q in content["quiz"]
        ]
    return form


def test_upload_save_restart_and_share_preserves_edits(demo):
    client, factory, fake, checkpoint = demo
    client.post("/login", data={"user_id": 1})
    assert client.get("/tutor").status_code == 200
    response = client.post(
        "/tutor/sessions",
        data={
            "title": "New algebra lesson",
            "student_id": 2,
            "previous_session_id": 1,
            "fallback_id": "2",
        },
        files={"video": ("Sample #2.mp4", b"test recording", "video/mp4")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    url = response.headers["location"]
    session_id = int(url.rsplit("/", 1)[-1])
    page = client.get(url)
    assert page.status_code == 200
    assert "draft" in page.text and "Compared with the previous session" in page.text
    assert fake.quiz_calls == 2
    with factory() as db:
        lesson = db.get(Session, session_id)
        assert lesson.status == "draft" and lesson.previous_session_id == 1
        assert "parentheses" in lesson.transcript
        content = output_dict(lesson.output)
    content.update(
        subject="Tutor subject",
        subtopics=["Tutor subtopic"],
        summary="Tutor's revised summary",
        progress_feedback="Tutor's revised feedback",
        strengths=["Tutor strength"],
        areas_to_improve=["Tutor improvement"],
    )
    content["quiz"][0].update(
        question="Tutor revised question",
        answer="4",
        explanation="Tutor revised explanation",
        difficulty="easier",
    )
    response = client.post(
        f"{url}/save", data=edit_form(content), follow_redirects=False
    )
    assert response.status_code == 303
    assert "Tutor revised question" in client.get(url).text
    with factory() as db:
        lesson = db.get(Session, session_id)
        assert lesson.status == "draft" and lesson.output.edited
        assert output_dict(lesson.output) == content
    # Restart the full pipeline object, not just a graph instance.
    client.app.state.pipeline.close()
    client.app.state.pipeline = Pipeline(checkpoint, lambda: fake)
    response = client.post(f"{url}/share", follow_redirects=False)
    assert response.status_code == 303
    with factory() as db:
        lesson = db.get(Session, session_id)
        assert lesson.status == "shared"
        assert output_dict(lesson.output) == content
        token = lesson.share_token
    client.post(f"{url}/share")
    with factory() as db:
        assert db.get(Session, session_id).share_token == token
    assert fake.quiz_calls == 2


def test_invalid_edits_do_not_replace_saved_content(demo):
    client, factory, _, _ = demo
    client.post("/login", data={"user_id": 1})
    with factory() as db:
        content = output_dict(db.get(Session, 1).output)
    form = edit_form(content)
    form["q_answer"][0] = "not an option"
    response = client.post("/tutor/sessions/1/save", data=form)
    assert response.status_code == 422
    assert "answer must exactly match" in response.text
    with factory() as db:
        assert output_dict(db.get(Session, 1).output) == content


def test_processing_poll_and_visible_failure(demo, monkeypatch):
    client, factory, fake, _ = demo
    client.post("/login", data={"user_id": 1})
    with factory.begin() as db:
        lesson = Session(
            tutor_id=1,
            student_id=2,
            title="Pending lesson",
            status="processing",
            transcript="equations",
        )
        db.add(lesson)
        db.flush()
        session_id = lesson.id
    url = f"/tutor/sessions/{session_id}?poll=true"
    response = client.get(url)
    assert 'hx-trigger="every 2s"' in response.text
    fake.invalid_attempts = 10
    client.app.state.pipeline.run(session_id)
    response = client.get(url)
    assert "after three attempts" in response.text
    assert "hx-trigger" not in response.text
    assert client.post(f"/tutor/sessions/{session_id}/share").status_code == 400


def test_upload_validates_student_previous_session_and_sample(demo):
    client, factory, _, _ = demo
    client.post("/login", data={"user_id": 1})
    for data in [
        {"title": "Test", "student_id": 1, "fallback_id": "1"},
        {
            "title": "Test",
            "student_id": 2,
            "fallback_id": "1",
            "previous_session_id": "999",
        },
        {"title": "Test", "student_id": 2, "fallback_id": "../1"},
    ]:
        assert client.post("/tutor/sessions", data=data).status_code == 400
    with factory() as db:
        assert len(db.scalars(select(Session)).all()) == 3
