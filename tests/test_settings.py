from app.models import Session, User


def test_booking_and_paid_changes_reach_student_and_public_page(demo):
    client, factory, _, _ = demo
    client.post("/login", data={"user_id": 1})
    assert (
        client.post(
            "/tutor/settings/calendly",
            data={"calendly_url": "https://calendly.com/alex/tutoring"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert (
        client.post("/tutor/sessions/1/paid", follow_redirects=False).status_code == 303
    )
    with factory() as db:
        lesson = db.get(Session, 1)
        assert not lesson.paid
        token = lesson.share_token
    client.post("/login", data={"user_id": 2})
    for url in ["/student/sessions/1", f"/share/{token}"]:
        page = client.get(url)
        assert "Unpaid" in page.text
        assert (
            'href="https://calendly.com/alex/tutoring"' in page.text
            and "Book Session" in page.text
        )
    assert client.post("/tutor/sessions/1/paid").status_code == 403
    client.post("/login", data={"user_id": 1})
    for url in [
        "javascript:alert(1)",
        "https://evil.example/",
        "https://calendly.com@evil.example/",
    ]:
        assert (
            client.post(
                "/tutor/settings/calendly", data={"calendly_url": url}
            ).status_code
            == 400
        )
    client.post("/tutor/settings/calendly", data={"calendly_url": ""})
    with factory() as db:
        assert db.get(User, 1).calendly_url is None
    assert "Book Session" not in client.get(f"/share/{token}").text
