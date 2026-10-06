# Usage

[← README](../README.md)

## Setup alternatives

The README quickstart uses PowerShell. On macOS/Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
cp .env.example .env  # first setup only
```

If PowerShell blocks activation, run the virtual environment's Python directly:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe seed.py
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Use one application worker. Open [localhost:8000/login](http://localhost:8000/login) after startup. Mocked login has no passwords: choose Alex for the tutor dashboard or Sam for the student vault.

## Demo walkthrough

1. Log in as **Alex (Tutor)**. Open a seeded lesson to inspect the summary, feedback, and quiz.
2. Create a new session for Sam. Choose **Linear equations: progress** as the sample transcript and **Example 1** as the previous session. In sample mode, uploading a recording is optional.
3. Submit the form. HTMX polls every two seconds until a draft or error is available. If the CDN script cannot load, use the manual refresh link.
4. Review the generated subject, subtopics, summary, previous-session comparison, strengths, areas to improve, and 3–5 quiz questions.
5. Edit any content field, including quiz options, answers, explanations, and difficulty. Click **Save edits**, then reload to verify persistence.
6. Click **Approve and share**. Open the displayed link without logging in, for example in an incognito window.
7. Log in as **Sam (Student)**. Open the shared session in the vault and reveal each quiz answer and explanation.
8. Return to Alex's dashboard. Save an `https://calendly.com/...` booking URL, then change a lesson's paid status. The student and public views show the updated booking button and payment badge.
9. With tracing configured, inspect the generation and resumed publication runs in LangSmith. Both use the session thread ID and include node-level traces.

Seeding creates three shared example sessions without making API calls. Example 2 links to Example 1. Seeded outputs are labeled example content; generating a new session exercises the actual model pipeline. Running `seed.py` again does not duplicate the accounts or example sessions.

## Editing and sharing

Save keeps a draft paused at tutor review. Share approves the latest saved version; save edits before clicking Share. A valid multiple-choice answer must exactly match one of four distinct options. Short-answer questions must have no options.

Invalid edits display an error without replacing the saved content. A processing or failed session cannot be shared. Published lessons appear in the student's vault and on their public link. Repeated sharing returns the same token.

Saving edits to an already-shared lesson updates its existing vault page and public link. The public page is read-only; it does not require login.

## Booking and payment status

The tutor dashboard accepts an HTTPS Calendly URL. It appears as **Book Session** in the student lesson view and public page. Leave the setting blank to remove the button. Booking opens Calendly in a new tab; the app does not create bookings or send emails.

The tutor can mark a session paid or unpaid. The badge updates for the tutor, student, and public page. It is a status flag, with no payment processing or content-access restriction.

## Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Startup check |
| GET | `/login` | Demo account selector |
| POST | `/login` | Set the signed-cookie user session |
| GET | `/logout` | Clear the user session |
| GET | `/tutor` | Tutor dashboard and booking settings |
| POST | `/tutor/sessions` | Upload or select a sample and start generation |
| GET | `/tutor/sessions/{id}` | Processing state, generated content, and editor |
| POST | `/tutor/sessions/{id}/save` | Validate and save edits |
| POST | `/tutor/sessions/{id}/share` | Resume review and publish |
| POST | `/tutor/sessions/{id}/paid` | Toggle the paid badge |
| POST | `/tutor/settings/calendly` | Save or remove the booking URL |
| GET | `/student` | Student's shared-session vault |
| GET | `/student/sessions/{id}` | Shared lesson and quiz |
| GET | `/share/{token}` | Public read-only lesson |

The student vault filters to the logged-in student's shared sessions. Basic route checks support the demo flow; mocked login is not production authentication. An invalid share token returns 404. Form validation failures return 422 with a visible error.

## Checks and evaluations

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
ruff check app scripts evals tests seed.py
ruff format --check app scripts evals tests seed.py
```

The 20 tests make no live API calls. They cover quiz repair/exhaustion, structured parsing errors, restart/resume, editing and publication, repeated sharing, publication recovery, vault filtering, public pages, transcript fallback, booking, paid badges, missing credentials, and the real DeepSeek adapter against mocked HTTP responses. Deterministic model doubles are injected only by tests; the application has no fake generation mode.

Run the three structured model nodes against a sample transcript:

```powershell
python -m scripts.run_agent --sample 2
```

Run the optional LangSmith dataset and evaluations:

```powershell
python evals/run_evals.py
```

The first command requires model credentials; evaluations require model and LangSmith credentials. The evaluation command creates `epistemy-sessions-synthetic-v1` if absent, then runs generation and quiz repair up to review. It checks quiz validity and uses a structured LLM judge for topic relevance and evidence-grounded progress or baseline feedback.

## Restart and failure recovery

Paused tutor reviews survive a server restart. Open the draft and Share normally afterward. Generation uses in-process background tasks, so processing interrupted by a restart needs explicit recovery.

Stop the web server, then resume the session by ID:

```powershell
python -m scripts.recover_session 4
```

Replace `4` with the affected processing session's ID, visible in its URL. Restart the server afterward. Recovery resumes from the last durable node checkpoint and preserves completed steps.

A session with no checkpoint must be uploaded again. An exhausted quiz loop also requires a new upload; its completed failure checkpoint cannot continue. If publication fails after approval, retry Share: it resumes publication using the latest saved edits without regenerating the lesson.

## Prototype assumptions

- Sample lessons use synthetic transcripts because the original assignment videos were not provided.
- First-session generated quiz difficulty is `same`, relative to the current lesson's baseline.
- A nullable `processing_error` supplements the three specified session statuses and stops polling on failure.
- HTMX is served from a pinned CDN URL; manual refresh, ordinary forms, and native answer reveal work without it.
- SQLAlchemy initializes tables with `create_all`; database migrations are not included.
- Paid status is informational and Calendly is an external link.
- PDF export is deferred; public share links satisfy the MVP's sharing requirement.
- Production authentication, payment gateways, queues, multi-process orchestration, and deployment configuration are outside scope.

Use Conventional Commits for repository changes: `feat(scope): ...`, `chore(scope): ...`, `refactor(scope): ...`, and `fix(scope): ...`.
