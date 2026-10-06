from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent.nodes import AgentNodes, output_from_state
from app.agent.state import SessionState
from app.schemas import EditedOutput


def human_review(state: SessionState) -> dict:
    decision = interrupt({"session_id": state["session_id"], "output": output_from_state(state)})
    if not isinstance(decision, dict) or decision.get("approved") is not True:
        raise ValueError("Publishing requires tutor approval.")
    content = EditedOutput.model_validate(decision["output"]).model_dump()
    return {
        "topics": {"subject": content["subject"], "subtopics": content["subtopics"]},
        "progress": {"summary": content["summary"], "feedback": content["progress_feedback"],
                     "strengths": content["strengths"], "areas_to_improve": content["areas_to_improve"]},
        "quiz": content["quiz"], "approved": True, "edited": bool(decision.get("edited")),
    }


def transcribe(state: SessionState) -> dict:
    if state.get("transcript", "").strip():
        return {}
    from app.services.transcription import transcribe_session

    return {"transcript": transcribe_session(state.get("video_path"), state.get("fallback_id"))}


def quiz_route(state: SessionState) -> str:
    if state.get("quiz_valid"):
        return "human_review"
    return "failed" if state.get("error") else "generate_quiz"


def build_graph(checkpointer, publish, model_factory=None):
    nodes = AgentNodes(model_factory) if model_factory else AgentNodes()
    graph = StateGraph(SessionState)
    graph.add_node("transcribe", transcribe)
    graph.add_node("extract_topics", nodes.extract_topics)
    graph.add_node("evaluate_progress", nodes.evaluate_progress)
    graph.add_node("generate_quiz", nodes.generate_quiz)
    graph.add_node("validate_quiz", nodes.validate_quiz)
    graph.add_node("human_review", human_review)
    graph.add_node("publish", publish)
    graph.add_node("failed", lambda state: {"approved": False})
    graph.add_edge(START, "transcribe")
    graph.add_edge("transcribe", "extract_topics")
    graph.add_edge("extract_topics", "evaluate_progress")
    graph.add_edge("evaluate_progress", "generate_quiz")
    graph.add_edge("generate_quiz", "validate_quiz")
    graph.add_conditional_edges("validate_quiz", quiz_route, ["generate_quiz", "human_review", "failed"])
    graph.add_edge("human_review", "publish")
    graph.add_edge("publish", END)
    graph.add_edge("failed", END)
    return graph.compile(checkpointer=checkpointer)
