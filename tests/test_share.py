from app.models import Session


def test_public_page_needs_no_login_and_escapes_tutor_content(demo):
    client, factory, _, _ = demo
    with factory.begin() as db:
        lesson = db.get(Session, 1)
        lesson.output.summary = "<script>alert('lesson')</script>"
        token = lesson.share_token
    response = client.get(f"/share/{token}")
    assert response.status_code == 200
    assert "&lt;script&gt;" in response.text and "<script>alert" not in response.text
    assert "Reveal answer and explanation" in response.text
    assert client.get("/share/unknown").status_code == 404
    with factory.begin() as db:
        db.get(Session, 1).status = "draft"
    assert client.get(f"/share/{token}").status_code == 404
