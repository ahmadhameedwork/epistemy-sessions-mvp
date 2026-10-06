import json
import sqlite3

import httpx
import pytest
from langchain.chat_models import init_chat_model
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.agent import model
from app.agent.graph import build_graph
from app.agent.nodes import output_from_state
from app.agent.state import initial_state
from app.config import Settings, settings
from tests.fakes import valid_quiz


def test_deepseek_key_is_loaded_from_dotenv(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "LLM_PROVIDER=deepseek\nLLM_MODEL=deepseek-flash\nDEEPSEEK_API_KEY=test-placeholder\n",
        encoding="utf-8",
    )
    config = Settings(_env_file=path)
    assert config.deepseek_api_key == "test-placeholder"


def test_missing_deepseek_key_has_provider_specific_error(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    with pytest.raises(ValueError, match="Set DEEPSEEK_API_KEY"):
        model.build_model()


def test_real_deepseek_adapter_parses_outputs_repairs_quiz_and_resumes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(settings, "llm_model", "deepseek-flash")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-placeholder")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "langsmith_tracing", False)
    calls = []
    quiz_calls = 0

    def respond(request):
        nonlocal quiz_calls
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.url.host == "api.deepseek.com"
        assert payload["model"] == "deepseek-flash"
        assert payload["thinking"] == {"type": "disabled"}
        assert payload["max_tokens"] == 4096
        name = payload["tool_choice"]["function"]["name"]
        if name == "TopicResult":
            result = {"subject": "Mathematics", "subtopics": ["Linear equations"]}
        elif name == "ProgressResult":
            result = {
                "summary": "Practiced equations.",
                "feedback": "No previous session is available; this is baseline feedback.",
                "strengths": ["Division"],
                "areas_to_improve": ["Distribution"],
            }
        else:
            assert name == "QuizResult"
            quiz_calls += 1
            questions = valid_quiz()
            if quiz_calls == 1:
                questions[0]["answer"] = "invalid"
            else:
                assert "answer must exactly match" in payload["messages"][-1]["content"]
            result = {"questions": questions}
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-test",
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": json.dumps(result),
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 10,
                    "total_tokens": 20,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(
            model,
            "init_chat_model",
            lambda *args, **kwargs: init_chat_model(
                *args, http_client=client, **kwargs
            ),
        )
        assert isinstance(model.build_model(), ChatDeepSeek)
        with sqlite3.connect(
            tmp_path / "checkpoint.db", check_same_thread=False
        ) as connection:
            published = []
            graph = build_graph(
                SqliteSaver(connection),
                lambda state: published.append(output_from_state(state)) or {},
                model.build_model,
            )
            config = {"configurable": {"thread_id": "session-deepseek"}}
            state = graph.invoke(initial_state(1, "Equations lesson"), config)
            assert state["__interrupt__"] and quiz_calls == 2
            content = output_from_state(state)
            content["summary"] = "Tutor-edited DeepSeek output"
            graph.invoke(
                Command(resume={"approved": True, "output": content, "edited": True}),
                config,
            )
    assert len(calls) == 4
    assert published[0]["summary"] == "Tutor-edited DeepSeek output"
