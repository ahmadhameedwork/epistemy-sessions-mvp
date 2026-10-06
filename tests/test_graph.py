import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.agent.graph import build_graph
from app.agent.nodes import output_from_state
from app.agent.state import initial_state
from tests.fakes import FakeModel


def test_quiz_repair_interrupt_restart_and_approved_edits(tmp_path):
    path = tmp_path / "checkpoint.db"
    fake = FakeModel(invalid_attempts=1)
    published = []

    def publish(state):
        published.append(output_from_state(state))
        return {"share_token": "stable-test-token"}

    config = {"configurable": {"thread_id": "session-42"}}
    with sqlite3.connect(path, check_same_thread=False) as conn:
        graph = build_graph(SqliteSaver(conn), publish, lambda: fake)
        result = graph.invoke(
            initial_state(42, "Current equations lesson", "Previous equations lesson"),
            config,
        )
        assert result["__interrupt__"]
        assert fake.quiz_calls == 2
        assert result["retries"] == 1
        assert not published
        assert "answer must exactly match" in fake.prompts[-1]
        approved = output_from_state(result)
        approved["summary"] = "Tutor corrected this summary."
    # Create a new graph and connection to simulate an application restart.
    with sqlite3.connect(path, check_same_thread=False) as conn:
        graph = build_graph(SqliteSaver(conn), publish, lambda: fake)
        result = graph.invoke(
            Command(resume={"approved": True, "output": approved, "edited": True}),
            config,
        )
    assert result["share_token"] == "stable-test-token"
    assert published[0]["summary"] == "Tutor corrected this summary."
    assert fake.quiz_calls == 2  # Publishing does not re-run the model.


def test_exhausted_quiz_never_reaches_review(tmp_path):
    fake = FakeModel(invalid_attempts=10)
    with sqlite3.connect(tmp_path / "checkpoint.db", check_same_thread=False) as conn:
        graph = build_graph(
            SqliteSaver(conn),
            lambda state: (_ for _ in ()).throw(AssertionError("Must not publish")),
            lambda: fake,
        )
        result = graph.invoke(
            initial_state(1, "Equations"), {"configurable": {"thread_id": "session-1"}}
        )
        assert fake.quiz_calls == 3
        assert "after three attempts" in result["error"]
        assert "__interrupt__" not in result
        assert not result["approved"]


def test_structured_parse_failure_is_repaired(tmp_path):
    fake = FakeModel(parse_failures=1)
    with sqlite3.connect(tmp_path / "checkpoint.db", check_same_thread=False) as conn:
        graph = build_graph(SqliteSaver(conn), lambda state: {}, lambda: fake)
        result = graph.invoke(
            initial_state(1, "Equations"), {"configurable": {"thread_id": "session-1"}}
        )
    assert result["__interrupt__"]
    assert fake.quiz_calls == 2
    assert "Missing required answer" in fake.prompts[-1]
