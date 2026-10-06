from langchain_core.runnables import RunnableLambda

from app.schemas import ProgressResult, QuizResult, TopicResult


def valid_quiz():
    return [
        dict(id=1, question="Solve 4x = 20.", type="multiple_choice", options=["4", "5", "16", "24"], answer="5", explanation="Divide both sides by four.", difficulty="same"),
        dict(id=2, question="Solve x - 3 = -8.", type="short_answer", options=None, answer="-5", explanation="Add three to both sides.", difficulty="same"),
        dict(id=3, question="Solve 3(x + 2) = 21.", type="short_answer", options=None, answer="5", explanation="Divide by three and subtract two.", difficulty="same"),
    ]


class FakeModel:
    """Only injected by tests; no fake model is available in the application."""

    def __init__(self, invalid_attempts=0, parse_failures=0):
        self.invalid_attempts = invalid_attempts
        self.parse_failures = parse_failures
        self.quiz_calls = 0
        self.prompts = []

    def with_structured_output(self, schema, include_raw=False):
        def respond(prompt):
            text = prompt.to_string()
            self.prompts.append(text)
            if schema is TopicResult:
                return TopicResult(subject="Mathematics", subtopics=["Linear equations", "Distribution"])
            if schema is ProgressResult:
                return ProgressResult(summary="Practiced equations and distribution.", feedback="Compared with the previous session, division improved; distribution is new." if "PREVIOUS TRANSCRIPT: No previous" not in text else "No previous session is available; this is baseline feedback.", strengths=["Division"], areas_to_improve=["Distribution"])
            assert schema is QuizResult
            self.quiz_calls += 1
            if self.quiz_calls <= self.parse_failures:
                return {"parsed": None, "parsing_error": ValueError("Missing required answer")}
            quiz = valid_quiz()
            if self.quiz_calls <= self.invalid_attempts:
                quiz[0]["answer"] = "999"
            parsed = QuizResult.model_validate({"questions": quiz})
            return {"parsed": parsed, "parsing_error": None} if include_raw else parsed
        return RunnableLambda(respond)
