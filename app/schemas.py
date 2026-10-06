from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Result(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class TopicResult(Result):
    subject: str = Field(min_length=1)
    subtopics: list[str] = Field(min_length=1)


class ProgressResult(Result):
    summary: str = Field(min_length=1)
    feedback: str = Field(min_length=1)
    strengths: list[str]
    areas_to_improve: list[str]


class QuizQuestion(Result):
    id: int = Field(gt=0)
    question: str = Field(min_length=1)
    type: Literal["multiple_choice", "short_answer"]
    options: list[str] | None
    answer: str = Field(min_length=1, description="For multiple choice, the exact text of one option.")
    explanation: str = Field(min_length=1)
    difficulty: Literal["easier", "same", "harder"]


class QuizResult(Result):
    questions: list[QuizQuestion]


def quiz_errors(questions: list[dict]) -> list[str]:
    """Deterministic checks used for generated questions and tutor edits."""
    errors = []
    if not 3 <= len(questions) <= 5:
        errors.append("Provide 3 to 5 questions.")
    ids = set()
    for index, value in enumerate(questions, 1):
        try:
            q = QuizQuestion.model_validate(value)
        except ValueError as exc:
            errors.append(f"Question {index}: {exc}")
            continue
        if q.id in ids:
            errors.append(f"Question {index}: question IDs must be unique.")
        ids.add(q.id)
        if q.type == "multiple_choice":
            options = q.options or []
            if len(options) != 4 or any(not item.strip() for item in options) or len(set(options)) != 4:
                errors.append(f"Question {index}: provide four distinct nonempty options.")
            if q.answer not in options:
                errors.append(f"Question {index}: answer must exactly match one option.")
        elif q.options:
            errors.append(f"Question {index}: short-answer questions must have no options.")
    return errors


class EditedOutput(Result):
    subject: str = Field(min_length=1, max_length=200)
    subtopics: list[str] = Field(min_length=1)
    summary: str = Field(min_length=1)
    progress_feedback: str = Field(min_length=1)
    strengths: list[str]
    areas_to_improve: list[str]
    quiz: list[QuizQuestion]

    @model_validator(mode="after")
    def valid_content(self):
        errors = quiz_errors([q.model_dump() for q in self.quiz])
        if any(not value.strip() for value in self.subtopics + self.strengths + self.areas_to_improve):
            errors.append("List entries cannot be blank.")
        if errors:
            raise ValueError(" ".join(errors))
        return self
