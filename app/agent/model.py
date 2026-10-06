import os

from langchain.chat_models import init_chat_model

from app.config import settings


def configure_tracing() -> None:
    os.environ["LANGSMITH_TRACING"] = str(
        settings.langsmith_tracing and bool(settings.langsmith_api_key)
    ).lower()
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key


def build_model():
    configure_tracing()
    options = {"timeout": 45, "max_retries": 2, "temperature": 0}
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError(
                "Set OPENAI_API_KEY in .env to generate a new lesson. Transcript fallback still requires an LLM key."
            )
        options["api_key"] = settings.openai_api_key
    elif settings.llm_provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError(
                "Set DEEPSEEK_API_KEY in .env to generate a new lesson with DeepSeek."
            )
        options["api_key"] = settings.deepseek_api_key
        # Structured output forces a named tool, which requires non-thinking mode.
        options["extra_body"] = {"thinking": {"type": "disabled"}}
        options["max_tokens"] = 4096
    return init_chat_model(
        settings.llm_model, model_provider=settings.llm_provider, **options
    )
