from app.models import Session, User


def test_vault_only_shows_students_shared_sessions(demo):
    client, factory, _, _ = demo
    with factory.begin() as db:
        other = User(name="Other student", email="other@example.com", role="student")
        db.add(other)
        db.flush()
        own_draft = Session(tutor_id=1, student_id=2, title="Own unshared draft", status="draft")
        other_lesson = Session(tutor_id=1, student_id=other.id, title="Other student's session", status="shared")
        db.add_all([own_draft, other_lesson])
        db.flush()
        draft_id, other_id = own_draft.id, other_lesson.id
    client.post("/login", data={"user_id": 2})
    page = client.get("/student")
    assert page.status_code == 200 and "Example 1" in page.text
    assert "Own unshared draft" not in page.text and "Other student&#39;s session" not in page.text
    assert client.get(f"/student/sessions/{draft_id}").status_code == 404
    assert client.get(f"/student/sessions/{other_id}").status_code == 404
    page = client.get("/student/sessions/1")
    assert "Reveal answer and explanation" in page.text and "Paid" in page.text
    assert client.get("/tutor").status_code == 403
