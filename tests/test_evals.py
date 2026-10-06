from types import SimpleNamespace

from evals.run_evals import examples, generate, quiz_evaluator
from tests.fakes import FakeModel


def test_eval_target_runs_real_graph_and_deterministic_quiz_evaluator():
    data = examples()
    assert len(data) == 3 and data[1]["inputs"]["previous_transcript"]
    model = FakeModel(invalid_attempts=1)
    result = generate(data[1]["inputs"], lambda: model)
    assessment = quiz_evaluator(SimpleNamespace(outputs=result), None)
    assert assessment["score"] == 1 and model.quiz_calls == 2
    assert "previous session" in result["progress_feedback"]
    result["quiz"][0]["answer"] = "invalid"
    assert quiz_evaluator(SimpleNamespace(outputs=result), None)["score"] == 0
