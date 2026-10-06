from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('tutor', 'student')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(250), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    calendly_url: Mapped[str | None] = mapped_column(String(500))


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint("status IN ('processing', 'draft', 'shared')"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tutor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    video_path: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str] = mapped_column(Text, default="")
    previous_session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    status: Mapped[str] = mapped_column(String(20), default="processing")
    paid: Mapped[bool] = mapped_column(Boolean, default=False)
    share_token: Mapped[str | None] = mapped_column(String(100), unique=True)
    processing_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    tutor: Mapped[User] = relationship(foreign_keys=[tutor_id])
    student: Mapped[User] = relationship(foreign_keys=[student_id])
    output: Mapped["SessionOutput | None"] = relationship(
        back_populates="session", uselist=False
    )


class SessionOutput(Base):
    __tablename__ = "session_outputs"

    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    subject: Mapped[str] = mapped_column(String(200))
    subtopics: Mapped[list] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text)
    progress_feedback: Mapped[str] = mapped_column(Text)
    strengths: Mapped[list] = mapped_column(JSON)
    areas_to_improve: Mapped[list] = mapped_column(JSON)
    quiz: Mapped[list] = mapped_column(JSON)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    session: Mapped[Session] = relationship(back_populates="output")
