import json

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from app.agent import prompts
from app.agent.model import build_model
from app.agent.state import SessionState
from app.schemas import ProgressResult, QuizResult, TopicResult, quiz_errors


class AgentNodes:
    def __init__(self, model_factory=build_model):
        self.model_factory = model_factory

    def extract_topics(self, state: SessionState) -> dict:
        chain = prompts.TOPICS | self.model_factory().with_structured_output(
            TopicResult
        )
        result = chain.invoke({"transcript": state["transcript"]})
        return {"topics": TopicResult.model_validate(result).model_dump()}

    def evaluate_progress(self, state: SessionState) -> dict:
        chain = prompts.PROGRESS | self.model_factory().with_structured_output(
            ProgressResult
        )
        result = chain.invoke(
            {
                "transcript": state["transcript"],
                "previous_transcript": state.get("previous_transcript")
                or "No previous session is available.",
                "topics": json.dumps(state["topics"]),
            }
        )
        return {"progress": ProgressResult.model_validate(result).model_dump()}

    def generate_quiz(self, state: SessionState) -> dict:
        chain = prompts.QUIZ | self.model_factory().with_structured_output(
            QuizResult, include_raw=True
        )
        try:
            result = chain.invoke(
                {
                    "transcript": state["transcript"],
                    "previous_transcript": state.get("previous_transcript")
                    or "No previous session is available.",
                    "topics": json.dumps(state["topics"]),
                    "progress": json.dumps(state["progress"]),
                    "validation_errors": "; ".join(state.get("validation_errors", []))
                    or "None; this is the first attempt.",
                }
            )
            if result.get("parsing_error") or result.get("parsed") is None:
                return {
                    "quiz": None,
                    "validation_errors": [
                        str(
                            result.get("parsing_error")
                            or "Model returned no structured quiz."
                        )
                    ],
                }
            parsed = QuizResult.model_validate(result["parsed"])
            return {
                "quiz": [q.model_dump() for q in parsed.questions],
                "validation_errors": [],
            }
        except (ValidationError, OutputParserException) as exc:
            return {"quiz": None, "validation_errors": [str(exc)]}

    def validate_quiz(self, state: SessionState) -> dict:
        errors = (
            list(state.get("validation_errors", []))
            if state.get("quiz") is None
            else quiz_errors(state["quiz"])
        )
        if not state.get("previous_transcript") and any(
            q["difficulty"] != "same" for q in state.get("quiz") or []
        ):
            errors.append(
                "Without a previous lesson, all difficulties must be same (baseline)."
            )
        if not errors:
            return {"quiz_valid": True, "validation_errors": [], "error": None}
        retries = state.get("retries", 0)
        if retries >= 2:
            return {
                "quiz_valid": False,
                "validation_errors": errors,
                "error": "Quiz validation failed after three attempts: "
                + " ".join(errors),
            }
        return {
            "quiz_valid": False,
            "validation_errors": errors,
            "retries": retries + 1,
        }


def output_from_state(state: SessionState) -> dict:
    return {
        "subject": state["topics"]["subject"],
        "subtopics": state["topics"]["subtopics"],
        "summary": state["progress"]["summary"],
        "progress_feedback": state["progress"]["feedback"],
        "strengths": state["progress"]["strengths"],
        "areas_to_improve": state["progress"]["areas_to_improve"],
        "quiz": state["quiz"],
    }
