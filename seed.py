"""Seed clearly labeled example content without making API calls."""
import secrets

from sqlalchemy import select

from app.config import ROOT
from app.db import SessionLocal, init_db
from app.models import Session, SessionOutput, User


def seed() -> None:
    init_db()
    with SessionLocal.begin() as db:
        tutor = db.scalar(select(User).where(User.email == "tutor@example.com"))
        if tutor is None:
            tutor = User(name="Alex (Tutor)", email="tutor@example.com", role="tutor")
            db.add(tutor)
        student = db.scalar(select(User).where(User.email == "student@example.com"))
        if student is None:
            student = User(name="Sam (Student)", email="student@example.com", role="student")
            db.add(student)
        db.flush()
        previous = None
        for index in range(1, 4):
            title = f"Example {index}: {'Linear equations' if index < 3 else 'Fractions'}"
            lesson = db.scalar(select(Session).where(Session.tutor_id == tutor.id, Session.title == title))
            if lesson is None:
                lesson = Session(
                    tutor_id=tutor.id, student_id=student.id, title=title,
                    transcript=(ROOT / f"data/transcripts/session-{index}.txt").read_text(encoding="utf-8"),
                    previous_session_id=previous.id if index == 2 else None,
                    status="shared", share_token=secrets.token_urlsafe(24), paid=index == 1,
                )
                db.add(lesson)
                db.flush()
                fractions = index == 3
                questions = [
                    ("What is one half plus one quarter?", ["1/4", "1/2", "3/4", "1"], "3/4", "One half is two quarters; adding one quarter gives three quarters."),
                    ("Simplify two sixths.", [], "1/3", "Divide numerator and denominator by two."),
                    ("What is two thirds plus one fourth?", [], "11/12", "Use twelfths: 8/12 + 3/12 = 11/12."),
                ] if fractions else [
                    ("Solve 4x = 20.", ["4", "5", "16", "24"], "5", "Divide both sides by four."),
                    ("Solve x - 3 = -8.", [], "-5", "Add three to both sides."),
                    ("Solve 2x + 4 = 14.", [], "5", "Subtract four, then divide by two."),
                ]
                db.add(SessionOutput(
                    session_id=lesson.id, subject="Mathematics",
                    subtopics=["Equivalent fractions", "Common denominators"] if fractions else ["Linear equations", "Inverse operations", "Signed arithmetic"],
                    summary="Example output: practiced equivalent fractions and common denominators." if fractions else "Example output: practiced solving and checking linear equations.",
                    progress_feedback="Example output: compared with the previous session, division and signed arithmetic improved; distribution is a new area to practice." if index == 2 else "Example output: no previous session is linked. This is baseline feedback.",
                    strengths=["Simplifying fractions" if fractions else "Checking answers by substitution"],
                    areas_to_improve=["Choosing common denominators" if fractions else "Distribution" if index == 2 else "Signed arithmetic"],
                    quiz=[dict(id=i, question=q, type="multiple_choice" if options else "short_answer", options=options or None, answer=answer, explanation=explanation, difficulty="same") for i, (q, options, answer, explanation) in enumerate(questions, 1)],
                ))
            previous = lesson
    print("Seeded tutor, student, and three shared example sessions (no API calls).")


if __name__ == "__main__":
    seed()
