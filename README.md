# Epistemy Sessions

A Python prototype for **tutoring lesson → AI summary, progress feedback, and quiz → tutor review → student vault**.

FastAPI serves Jinja2 templates with HTMX polling. LangChain supplies typed model calls; LangGraph manages quiz repair, persistent tutor review, and publication. SQLite stores application data and graph checkpoints. LangSmith provides tracing and optional evaluations.

## Setup

Python **3.11+** is required. Run commands from the repository root.

```powershell
git clone https://github.com/ahmadhameedwork/epistemy-sessions-mvp.git
cd epistemy-sessions-mvp
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python seed.py
uvicorn app.main:app --reload
```

On macOS/Linux, activate with `source .venv/bin/activate` and copy the configuration with `cp .env.example .env`. If PowerShell blocks activation, use `.venv\Scripts\python.exe -m pip` and `.venv\Scripts\python.exe -m uvicorn` directly instead.

Open **http://127.0.0.1:8000/login**. Choose Alex (tutor) or Sam (student). The seed script is idempotent and makes no API calls; it creates three already-shared sessions with clearly labeled example outputs. Session 2 links to Session 1.

## Configure AI generation

Set these values in your local `.env`:

```dotenv
OPENAI_API_KEY=your-key
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
USE_FALLBACK_TRANSCRIPTS=true
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=epistemy-sessions
```

**Transcript fallback replaces transcription only. New generated content still requires an LLM API key.** Without keys, login, seeded sessions, editing, booking controls, paid status, and public links work. New generation displays a configuration error instead of fabricating AI output.

### DeepSeek instead of OpenAI

Keep your API key in the ignored local `.env` file; do not paste it into chat or commit it.
For DeepSeek generation, use:

```dotenv
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-flash
DEEPSEEK_API_KEY=your-key
USE_FALLBACK_TRANSCRIPTS=true
```

Restart the app after changing `.env`. No OpenAI key is required in this mode.
`langchain-deepseek` is included in the requirements. The app uses LangChain's
Pydantic structured output through tool calling and explicitly disables thinking
mode because the current DeepSeek API rejects forced tool choices in thinking mode.
The same quiz repair and human-review graph runs for either provider.
See [DeepSeek's model list](https://api-docs.deepseek.com/quick_start/pricing/) and
[tool calling documentation](https://api-docs.deepseek.com/api/create-chat-completion/).

DeepSeek supplies lesson analysis, not Whisper transcription. Keep sample transcript
mode enabled without an OpenAI key. Live DeepSeek responses require your credentials;
automated tests exercise its actual LangChain adapter against mocked HTTP responses.

For other model providers, install their LangChain integration, set `LLM_PROVIDER` and `LLM_MODEL`, and supply the provider's credentials using its documented environment variables. The chosen chat model must support `with_structured_output`. OpenAI and DeepSeek integrations are installed; other providers have not been verified. OpenAI remains the default in `.env.example` to match the build specification.

Tracing is enabled when `LANGSMITH_TRACING=true` and a LangSmith key is present; otherwise it is disabled so the seeded app can run without tracing credentials. `.env` settings are loaded into the tracing environment. Non-default LangSmith regions can additionally set `LANGSMITH_ENDPOINT` in the shell environment before starting the app.

## Demo walkthrough

1. Log in as Alex and open an example session to inspect its summary, feedback, and quiz.
2. On the dashboard, create a new session for Sam. Choose **Linear equations: progress** as the sample transcript, and Example 1 as its previous session. In sample mode a recording is optional; you can also upload your sample recording.
3. Submit and watch the processing page. HTMX polls every two seconds until a draft or error is available. A manual refresh link is also provided.
4. Review the generated topics, summary, comparison with the previous lesson, strengths, areas to improve, and 3–5 quiz questions.
5. Edit any content field, including quiz options, answers, explanations, and difficulty. Click **Save edits**. Reload to confirm the edits persisted.
6. Click **Approve and share**. Open the displayed link in an incognito window; no login is required.
7. Log in as Sam. Open the shared lesson from the vault and reveal quiz answers and explanations.
8. Log back in as Alex. Save an `https://calendly.com/...` booking URL and toggle the lesson's payment status. Both changes appear in the student view and public page.
9. With LangSmith configured, inspect the session run: transcription, topic extraction, progress assessment, quiz generation/validation, and tutor review. Publication appears in the resumed run under the same session thread and metadata.

**Save keeps a draft paused. Share approves the latest saved content.** Save changes before clicking Share. Saving edits to an already-shared lesson updates its existing vault page and share link. Repeated Share submissions reuse the same token.

## Agent workflow

```text
START → transcribe → extract_topics → evaluate_progress → generate_quiz
                                                           ↓
                                                     validate_quiz
                                              invalid ↗    ↓ valid
                                                   human_review (interrupt)
                                                           ↓ tutor shares
                                                        publish → END
```

Each LLM node uses Pydantic structured output. Quiz parsing failures and deterministic validation errors both enter the repair loop, with the specific errors supplied to the next attempt. There are at most **three attempts: the initial generation plus two retries**. Exhaustion stops before review/publication and produces a visible error.

Progress assessment receives both transcripts and requests evidence for improvement, repeated difficulty, and new topics. Quiz generation receives the transcript, topics, feedback, and previous-session context. Without a previous session, feedback states that it is a baseline and generated quiz difficulty is `same` relative to the current lesson.

`thread_id=session-{id}` identifies durable execution. `epistemy.db` holds editable content, while `checkpoints.db` holds execution state. Both are local ignored files. The application keeps its SQLite checkpointer connection open during its lifespan. Background jobs open their own SQLAlchemy sessions and do not hold transactions across LLM calls.

## Recordings and sample transcripts

The repository includes **three synthetic transcripts**, with a meaningful first-to-second lesson comparison. Original assignment videos were not present and are not distributed. Large recordings must not be committed.

In fallback mode, choose a sample explicitly. Its transcript is used instead of the uploaded recording. Choose a transcript matching your recording; the app does not infer this relationship from a filename.

To use Whisper, set `USE_FALLBACK_TRANSCRIPTS=false` and upload a supported recording: mp4, mp3, mpeg, mpga, m4a, wav, or webm. The app calls `whisper-1`. Uploads are capped at 25,000,000 bytes. If Whisper fails, only an explicitly selected sample fallback is used; otherwise a visible error is shown. Audio extraction, splitting long recordings, and transcript chunking are outside this prototype.

Uploaded files are saved under ignored `data/uploads/`. The existing `data/videos/` folder is available for local sample recordings.

## Checks and evaluations

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
ruff check app scripts evals tests seed.py
ruff format --check app scripts evals tests seed.py
```

Tests use deterministic model doubles injected into the actual LangGraph graph and FastAPI application. They cover repair and exhaustion, structured parsing errors, restart/resume, complete editing and publication, repeated sharing, publication recovery, vault filtering, public pages, transcript fallback, booking, and payment badges. The application has no fake AI generation mode.

Run the three real structured model calls against a sample transcript:

```powershell
python -m scripts.run_agent --sample 2
```

Run the optional LangSmith dataset and evaluations:

```powershell
python evals/run_evals.py
```

The evaluation command requires LLM and LangSmith credentials. It creates the versioned `epistemy-sessions-synthetic-v1` dataset if absent, then runs the real generation graph up to tutor review. Evaluators check quiz validity and use a structured LLM judge for topic relevance and evidence-grounded progress/baseline feedback. LLM judgments are useful development signals, not proof of pedagogical correctness.

## Restart and failure recovery

The app uses in-process FastAPI background tasks, as specified. They are not a durable work queue. A paused tutor review survives restart and can be shared normally, but a processing job interrupted by a restart must be resumed explicitly.

Stop the web server first, then run:

```powershell
python -m scripts.recover_session 4
```

Restart the web server afterward. The command resumes from the last durable node checkpoint, without rerunning completed nodes. A session with no checkpoint or an exhausted quiz repair loop must be uploaded again. If publication fails after approval, retry Share; it resumes publication using the latest saved edits.

Use one application worker. Per-session locks prevent simultaneous saves/shares in this process. Multi-process orchestration and queues are deliberately outside scope.

## Scope and assumptions

- Login is a signed-cookie user selector, with no passwords or real authentication.
- Basic route filtering keeps draft sessions out of the student vault; this is a local prototype, not a production permissions system.
- `paid` is a badge controlled by the tutor, with no payment processing or access restriction.
- Calendly is an external HTTPS link; there is no booking API or email integration.
- MC answers must match one of four distinct options. Short-answer questions have no options. Tutor edits undergo the same validation as generated quizzes.
- A nullable `processing_error` field supplements the specified three session statuses and stops endless polling on failures.
- Original videos are optional local files. Seed content is explicitly example content; generating a new lesson exercises the real model pipeline.
- HTMX is loaded from a pinned CDN URL. Without access to that CDN, use the manual refresh link; ordinary forms and native answer-reveal controls continue to work.
- Database tables are initialized with `create_all`; schema migrations are outside scope.
- PDF export is deferred. Public share links satisfy the export requirement.
- No SPA, queues, caching, payment gateway, deployment configuration, or frontend animation.

Never commit `.env`, database/checkpoint files, or recordings. Use Conventional Commits: `feat(scope): ...`, `chore(scope): ...`, `refactor(scope): ...`, and `fix(scope): ...`.
