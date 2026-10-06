# Configuration

[← README](../README.md)

Application settings are loaded from environment variables and the repository-root `.env` file. [.env.example](../.env.example) contains the supported settings without credentials. Copy it only during first setup; preserve an existing local `.env`.

## Settings

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `openai` | LangChain chat-model provider |
| `LLM_MODEL` | `gpt-4o-mini` | Model used by all generation nodes and the evaluation judge |
| `OPENAI_API_KEY` | Empty | OpenAI generation and live Whisper transcription |
| `DEEPSEEK_API_KEY` | Empty | DeepSeek generation |
| `LANGSMITH_TRACING` | `true` | Enables tracing when a LangSmith key is also present |
| `LANGSMITH_API_KEY` | Empty | LangSmith tracing and evaluations |
| `LANGSMITH_PROJECT` | `epistemy-sessions` | Project for application traces |
| `DATABASE_URL` | `sqlite:///./epistemy.db` | Application database |
| `CHECKPOINT_DB_PATH` | `./checkpoints.db` | Persistent LangGraph checkpoint database |
| `SECRET_KEY` | `dev-secret` | Signature key for the mocked login cookie |
| `USE_FALLBACK_TRANSCRIPTS` | `true` | Uses the explicitly selected sample transcript instead of Whisper |

Restart the app after changing settings. Run commands from the repository root so relative database paths remain consistent.

## DeepSeek

```dotenv
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-flash
DEEPSEEK_API_KEY=your-key
USE_FALLBACK_TRANSCRIPTS=true
```

This configuration requires no OpenAI key. The installed `langchain-deepseek` integration supplies Pydantic structured output through tool calling. The provider factory explicitly disables thinking mode because forced tool choices require non-thinking mode on the current DeepSeek API. Output is capped at 4,096 tokens per call.

The same progress assessment, quiz repair, and human-review graph runs with either provider. DeepSeek performs lesson analysis; it does not replace the OpenAI Whisper transcription service. Keep sample transcript mode enabled when using only a DeepSeek key.

References: [DeepSeek model list](https://api-docs.deepseek.com/quick_start/pricing/) and [chat-completion/tool-choice contract](https://api-docs.deepseek.com/api/create-chat-completion/).

## OpenAI

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your-key
USE_FALLBACK_TRANSCRIPTS=true
```

OpenAI remains the default in the example configuration to match the build specification. To transcribe an actual recording with `whisper-1`, set `USE_FALLBACK_TRANSCRIPTS=false` and upload a supported file.

Both provider integrations are included in `requirements.txt`. Other providers require their LangChain integration package, a compatible model, and credentials in the shell environment. The selected model must support `with_structured_output`; other integrations have not been verified for this app.

## Transcripts and recordings

The repository includes three synthetic transcripts: a baseline equations lesson, a follow-up equations lesson, and a baseline fractions lesson. The follow-up provides explicit evidence of progress from the first lesson. Original assignment videos are not distributed.

When `USE_FALLBACK_TRANSCRIPTS=true`, the tutor must choose a sample transcript. Its text is used instead of transcribing the recording; the recording itself is optional. The sample should match the intended lesson. The app does not infer a transcript from the recording's filename.

When fallback mode is disabled, a recording is required. Supported formats are **mp4, mp3, mpeg, mpga, m4a, wav, and webm**, with an upload limit of **25,000,000 bytes**. If Whisper fails, the app uses only an explicitly selected sample fallback. Without one, it displays a transcription error.

Transcript fallback replaces transcription only. New generation always requires a model-provider key. Without that key, the seeded sessions remain usable, while new generation displays a configuration error.

Audio extraction, long-recording splitting, and transcript chunking are outside the prototype.

## LangSmith

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=epistemy-sessions
```

Tracing is enabled only when both the flag and a key are present. With no key, tracing is disabled so the seeded app runs without telemetry credentials. The provider factory transfers the tracing settings from `.env` to the SDK environment.

For a non-default LangSmith region, set `LANGSMITH_ENDPOINT` in the shell environment before starting the app. Evaluations additionally require the selected model provider's credentials.

## Local files

`.env`, application and checkpoint databases, uploaded recordings, and large local sample videos are ignored by Git. Keep API keys in `.env`; leave all API-key values blank in `.env.example`.

Uploaded recordings are stored under `data/uploads/`. Local sample recordings can be placed in `data/videos/`. Neither folder's recordings should be committed.
