# Epistemy Sessions

UPLOAD. REVIEW. SHARE.

A tutoring-session web app with AI feedback, progression-aware quizzes, and a student vault.

[Architecture](docs/architecture.md) · [Configuration](docs/configuration.md) · [Usage](docs/usage.md)

---

## What it is

A FastAPI application that turns a tutoring recording or sample transcript into a lesson summary, progress feedback, and a 3–5 question quiz. Tutors review and edit the result before sharing it. Students open published lessons in their vault or through a public link, reveal quiz answers, and follow the tutor's Calendly booking link.

LangChain supplies Pydantic structured model calls. LangGraph runs the multi-step workflow, repairs invalid quizzes, and pauses for tutor approval with persistent SQLite checkpoints. DeepSeek and OpenAI are supported; LangSmith records the generation and resumed publication runs. The frontend uses Jinja2, HTMX, and plain CSS.

## Quickstart

Requires **Python 3.11+**. Runs as a single FastAPI process. These commands are for PowerShell:

```powershell
git clone https://github.com/ahmadhameedwork/epistemy-sessions-mvp.git
cd epistemy-sessions-mvp

python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

Copy-Item .env.example .env             # first setup; configure your provider below
python seed.py                         # demo accounts and three example lessons
python -m uvicorn app.main:app --reload # web app on :8000
```

On macOS/Linux, use `source .venv/bin/activate` and `cp .env.example .env`. If PowerShell blocks activation, use the virtual environment's Python directly; see [setup alternatives](docs/usage.md#setup-alternatives).

Open **[localhost:8000/login](http://localhost:8000/login)**. Choose **Alex (Tutor)** to manage lessons or **Sam (Student)** to open the vault. Verify startup at [`/health`](http://localhost:8000/health), which returns `{"status":"ok"}`. Interactive API documentation is at [`/docs`](http://localhost:8000/docs).

The seeded examples work without API keys. Generating a new lesson requires a model-provider key.

## Configuration

All application settings are environment variables loaded from `.env`; [.env.example](.env.example) is the canonical list. For DeepSeek generation with the included sample transcripts:

```dotenv
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-flash
DEEPSEEK_API_KEY=your-key
USE_FALLBACK_TRANSCRIPTS=true
```

Restart the app after changing configuration. Keep keys in the ignored `.env` file. Sample transcript mode requires no OpenAI key; live Whisper transcription does. LangSmith tracing is optional and needs `LANGSMITH_API_KEY` with `LANGSMITH_TRACING=true`.

See [configuration](docs/configuration.md) for defaults, OpenAI setup, transcription behavior, and local data paths.

## Usage

Log in as the tutor, create a session for Sam, and select a sample transcript. To demonstrate progress comparison, choose **Linear equations: progress** and link **Example 1** as the previous session. The processing page refreshes until a draft is ready.

Edit the generated content, click **Save edits**, then **Approve and share**. Save keeps the draft paused; Share publishes the latest saved content. Open the share link without login or switch to the student account to view it in the vault.

The [usage guide](docs/usage.md) covers the full walkthrough, routes, payment badges, booking links, and restart recovery.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q                    # 20 tests; no live API calls
ruff check app scripts evals tests seed.py
ruff format --check app scripts evals tests seed.py
```

Run the structured model nodes against a sample with `python -m scripts.run_agent --sample 2`. Run the optional LangSmith dataset and evaluators with `python evals/run_evals.py`; both commands require the corresponding API credentials. See [checks and evaluations](docs/usage.md#checks-and-evaluations).

## Scope

This is a tutoring-session prototype. Login is mocked, payment is a tutor-controlled paid/unpaid badge, and Calendly is an external link. The included lessons use synthetic transcripts and labeled example outputs; original assignment recordings are not distributed.

Use one application worker. Background generation runs in-process; paused reviews persist across restarts, while interrupted processing requires the [recovery command](docs/usage.md#restart-and-failure-recovery). PDF export, production authentication, payment processing, queues, and deployment configuration are outside the implemented MVP.
