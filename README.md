# PLAN.md — Sprint 1 (Starting from Scratch)

## Voice-Based Email & Messaging Assistant

---

## Sprint Overview

| Field                        | Details                                                                                                                                                                                    |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Sprint Number**            | Sprint 1 of 6                                                                                                                                                                              |
| **Duration**                 | 5 working days (1 week)                                                                                                                                                                    |
| **Scrum Master & Tech Lead** | Vivek Badodiya                                                                                                                                                                             |
| **Sprint Goal**              | Repo is live with branch strategy, Flask app runs locally, SQLite DB with User model, auth routes (login/signup) work with bcrypt, CI pipeline is green, base frontend templates in place. |
| **Status**                   | 🔄 Not Started                                                                                                                                                                             |

---

## Team & Roles

| Member                  | Role                                 | Notes                                                |
| ----------------------- | ------------------------------------ | ---------------------------------------------------- |
| **Vivek Badodiya**      | Scrum Master + Tech Lead             | Ceremonies, repo setup, PLAN.md, reviews, unblocking |
| Urmila Uttam Barkade    | Backend Developer 1                  | Flask app factory, auth routes, bcrypt               |
| Tummala Narasimhulu     | Backend Developer 2 + AI/ML Engineer | Models, DB, NLP stubs (dual role)                    |
| Penke Durga Prasad      | Frontend Developer 1                 | HTML templates, CSS                                  |
| Jagadeesh               | Frontend Developer 2 + Testing Lead  | error.html, pytest tests                             |
| Saniya Sulthana / Kiran | DevOps Engineer                      | CI/CD pipeline, .env setup                           |

---

## Sprint Ceremonies

| Ceremony             | When                | Duration | Owner |
| -------------------- | ------------------- | -------- | ----- |
| Sprint Planning      | Day 1 — 9:00 AM     | 1 hour   | Vivek |
| Daily Stand-up       | Every day — 9:30 AM | 15 min   | Vivek |
| Sprint Review        | Day 5 — 2:00 PM     | 45 min   | Vivek |
| Sprint Retrospective | Day 5 — 3:00 PM     | 30 min   | Vivek |

---

# Sprint Backlog – Day by Day

## Day 1 – Monday (Environment & Barebones)

**Goal:** Repo structure, Flask runs locally, SQLite connected, base templates.

### 🟣 Vivek (Scrum Master + Tech Lead)

- [ ] Create GitHub repo `voice-email-assistant` (already done, but ensure clone works).
- [ ] Define branch strategy: `main` (production), `dev` (integration), `feature/*`.
- [ ] Push initial `README.md` and this `PLAN.md`.
- [ ] Create `.gitignore` with `__pycache__/`, `*.pyc`, `.env`, `data.db`, `instance/`, `.coverage`, `htmlcov/`.

### 🔵 Urmila (Backend Dev 1)

- [ ] Set up Flask app factory in `src/app.py` with `/health` route.
- [ ] Verify app runs locally: `python run.py` → `http://localhost:5000/health` returns `{"status":"ok"}`.

### 🟢 Tummala (Backend Dev 2)

- [ ] Initialize SQLAlchemy in `src/db.py` (engine, session, `init_db()` stub).
- [ ] Create stub `src/models.py` with empty `User` class.
- [ ] Connect SQLite to Flask app in `src/app.py`.

### 🟠 Penke (Frontend Dev 1)

- [ ] Create `templates/base.html` with navigation (Home, Login, Signup) and placeholder content.
- [ ] Add `static/css/style.css` with CSS reset and basic styling.

### 🟡 Jagadeesh (Testing Lead + FE Dev 2)

- [ ] Create `templates/error.html` (generic error page).
- [ ] Write `test/test_app.py` with a simple test for `/health` endpoint.

### 🩷 Tummala (AI/ML – optional spike)

- [ ] Verify HuggingFace environment can load `flan-t5-small` locally (no code commit needed – just exploration).

### 💜 Saniya / Kiran (DevOps)

- [ ] Configure `.github/workflows/python-app.yml` with basic CI (install dependencies, run pytest).

---

## Day 2 – Tuesday (Auth Routes & User Model)

**Goal:** User model complete, bcrypt hashing, login/signup endpoints, basic forms.

### 🟣 Vivek

- [ ] Review Day 1 commits, ensure branch strategy is followed.
- [ ] Update `PLAN.md` with any changes.

### 🔵 Urmila

- [ ] Implement login & signup routes in `src/web/auth_routes.py`.
- [ ] Use bcrypt password hashing (create `src/services/auth.py` with `hash_password`, `verify_password`).
- [ ] Connect routes to `User` model (import from `models.py`).

### 🟢 Tummala (Backend Dev 2)

- [ ] Flesh out `models.py` with full `User` model: `id`, `email`, `password_hash`, `created_at`.
- [ ] Write a simple migration script or use `init_db()` to create `users` table.
- [ ] Verify DB connection with SQLite (e.g., `data.db` appears).

### 🟠 Penke

- [ ] Build `templates/login.html` (email + password form, OAuth button placeholder).
- [ ] Build `templates/signup.html` (similar, with client‑side validation).
- [ ] Connect both to `base.html` layout.

### 🟡 Jagadeesh

- [ ] Write pytest tests for `/login` and `/signup` (valid + invalid cases) in `test/test_auth_phase1.py`.
- [ ] Expand test suite to cover duplicate email, missing fields.

### 🩷 Tummala (AI/ML)

- [ ] Create stub `src/services/nlp_service.py` with `summarize_text()` and `suggest_replies()` (return placeholder strings/lists).
- [ ] Add a placeholder test script to verify HuggingFace model loads (optional).

### 💜 Saniya / Kiran

- [ ] Update CI pipeline to run auth tests.
- [ ] Add `.env.example` with `FLASK_SECRET_KEY`, `DATABASE_URL`.
- [ ] Ensure pipeline passes (may require mocking or environment variables).

---

## Day 3 – Wednesday (Session, Dashboard, UserToken, Voice Stub)

**Goal:** Session management, dashboard route, UserToken & EmailMessage models, voice transcription stub, test coverage.

### 🟣 Vivek

- [ ] Review and merge Day 2 PRs into `dev`, resolve any conflicts on `models.py`.
- [ ] Implement `/auth/logout` (clear session, return 200) and `/auth/status` (return user info or 401) in `auth_routes.py`.
- [ ] Enforce consistent JSON error response shape: `{"error": "...", "code": <status>}` across all auth routes.

### 🔵 Urmila

- [ ] Add session management to login/signup: set `session['user_id']` and `session['user_email']` on success.
- [ ] Add `/dashboard` route (auth‑guarded): render `dashboard.html` if session active, else redirect to `/auth/login`.
- [ ] Add input validation to signup/login: return HTTP 400 for missing fields, HTTP 409 for duplicate email.

### 🟢 Tummala (Backend Dev 2)

- [ ] Add `UserToken` model to `models.py`: `id`, `user_id` (FK), `service`, `access_token`, `refresh_token`, `expires_at`, `created_at`.
- [ ] Add `EmailMessage` model stub: `id`, `user_id` (FK), `gmail_id`, `subject`, `body`, `to`, `created_at`.
- [ ] Run `init_db()` and confirm 3 tables exist: `users`, `user_tokens`, `email_messages`.

### 🟠 Penke

- [ ] Build `templates/dashboard.html` shell: three‑column layout (sidebar | inbox | voice panel), empty state, hardcoded service status (Gmail 🔴 / Telegram 🔴).
- [ ] Update `base.html` nav: show Compose, Settings, Logout only when `session.user_id` is present.
- [ ] Add dashboard CSS: CSS Grid (`250px 1fr 300px`), responsive single‑column below 768px.

### 🟡 Jagadeesh

- [ ] Write tests for session management: login → session set → `/auth/status` returns user info.
- [ ] Write test for auth guard: `/dashboard` without session → 302 redirect to `/auth/login`.
- [ ] Write test for `/auth/logout`: login → logout → `/auth/status` returns 401.

### 🩷 Tummala (AI/ML)

- [ ] Implement `transcribe_audio(file_path, language=None)` stub in `src/services/voice.py` using `whisper.load_model("tiny")`. Return `{"text": ..., "language": ..., "segments": [...]}`.
- [ ] Write unit test for `transcribe_audio` that mocks `whisper.load_model` and `model.transcribe`.

### 💜 Saniya / Kiran

- [ ] Add per‑test in‑memory SQLite fixture to `test/conftest.py` to prevent shared DB state.
- [ ] Confirm CI still passes after new tests are added; check no session or DB leakage.

---

## Day 4 – Thursday (Telegram Models, Compose Page, NLP Routes)

**Goal:** Conversation & Message models, settings page, NLP routes wired, compose page stub.

### 🟣 Vivek

- [ ] Review and merge Day 3 PRs into `dev`.
- [ ] Create `templates/settings.html` shell: Gmail section ("Connect Gmail" button placeholder), Telegram token input form, service status display.
- [ ] Add `/settings` GET route (auth‑guarded) in `auth_routes.py` that renders `settings.html`.
- [ ] Triage any open bugs from Day 3 stand‑up.

### 🔵 Urmila

- [ ] Wire email route stubs (e.g., in `src/web/email_routes.py` or inside `auth_routes.py`):
  - `/email/send` (POST) → `{"status": "queued"}`
  - `/email/list` (GET) → `{"emails": []}`
  - `/email/read/<id>` (GET) → `{"error": "not implemented"}`, HTTP 501
- [ ] Write unit tests for all three stubs (auth guard, response shape).

### 🟢 Tummala (Backend Dev 2)

- [ ] Add `Conversation` model: `id`, `user_id` (FK), `telegram_chat_id` (unique), `state`, `context`, `created_at`, `updated_at`.
- [ ] Add `Message` model: `id`, `conversation_id` (FK), `sender` (user/bot), `text`, `created_at`.
- [ ] Confirm all 5 tables exist in `data.db`: `users`, `user_tokens`, `email_messages`, `conversations`, `messages`.

### 🟠 Penke

- [ ] Build `templates/compose.html` stub: service selector (Gmail/Telegram), recipient field, subject field (hide for Telegram), message textarea, Send button (non‑functional).
- [ ] Add voice dictation section: Record button, Stop button, transcription preview area (non‑functional – wired in Sprint 3).
- [ ] Wire compose page into `base.html` Compose nav link.

### 🟡 Jagadeesh

- [ ] Write tests for email route stubs: `/email/send`, `/email/list`, `/email/read/1` (401 without session, correct stub response with session).
- [ ] Write test: create a `Conversation` + 2 `Message` records, query `conversation.messages`, assert both returned in correct order.
- [ ] Run full test suite locally and report coverage % to Vivek.

### 🩷 Tummala (AI/ML)

- [ ] Wire `/nlp/summarize` route in `src/app.py`: accept `{text}` JSON, call `nlp_service.summarize_text()`, return `{"summary": ...}`.
- [ ] Wire `/nlp/suggest` route similarly: accept `{text}` JSON, return `{"suggestions": [...]}`.
- [ ] Write unit tests for both NLP routes (mock service functions, test response shape).

### 💜 Saniya / Kiran

- [ ] Add any new packages (bcrypt, openai-whisper, transformers, gTTS, torch) to `requirements.txt`.
- [ ] Verify CI pipeline installs all dependencies cleanly; mock `whisper` and HuggingFace model load in CI to prevent timeouts.
- [ ] Add CI step: fail build if coverage drops below 50% (baseline for this sprint).

---

## Day 5 – Friday (Integration, Bug Fixes, Sprint Review)

**Goal:** All code merged, integration bugs fixed, demos prepared, ceremonies held.

### 🟣 Vivek

- [ ] Merge all Day 4 PRs into `dev`, resolve conflicts (especially `models.py` and `app.py`).
- [ ] Fix any P1 integration bugs discovered after full merge.
- [ ] Write a Dockerfile scaffold (`FROM python:3.11-slim`, copy files, install deps, expose 5000, CMD flask run) – commit for Sprint 5 reference.
- [ ] Update `docs/SETUP_GUIDE.md` with any new setup steps (ffmpeg, model env vars).
- [ ] Facilitate Sprint Review (45 min) and Sprint Retrospective (30 min).

### 🔵 Urmila

- [ ] Fix any auth route bugs from integration (session not persisting, redirect loops, missing imports).
- [ ] Prepare 2‑minute demo: POST `/auth/signup` in browser → user in DB → login → session active → dashboard.

### 🟢 Tummala (Backend Dev 2)

- [ ] Fix any model FK or table creation bugs from integration.
- [ ] Prepare 2‑minute demo: show all 5 tables in `sqlite3` CLI or DB browser.

### 🟠 Penke

- [ ] Fix any Jinja2 rendering issues (template inheritance errors, broken static file paths).
- [ ] Prepare 2‑minute demo: login page → signup → redirect to dashboard shell → compose page layout.

### 🟡 Jagadeesh

- [ ] Run full test suite on merged `dev` branch, confirm zero failures.
- [ ] Prepare Sprint Review test summary: total tests written, pass rate, coverage %.
- [ ] Fix any failing tests from integration; document known gaps as GitHub issues.

### 🩷 Tummala (AI/ML)

- [ ] Confirm NLP stubs respond correctly after integration: `/nlp/summarize` and `/nlp/suggest` return expected shape.
- [ ] Prepare 2‑minute demo: call `summarize_text()` in Python REPL on a sample email body.

### 💜 Saniya / Kiran

- [ ] Final CI run on merged `dev` – all tests green, coverage report as artifact.
- [ ] Confirm Dockerfile builds without errors locally.

---

## Sprint Review Agenda (Friday 2:00 PM)

| #   | Demo                                                   | Owner          | Time  |
| --- | ------------------------------------------------------ | -------------- | ----- |
| 1   | Sprint goal recap                                      | Vivek          | 2 min |
| 2   | Signup → Login → Dashboard redirect                    | Urmila         | 2 min |
| 3   | All 5 DB tables exist, FK relationships                | Tummala        | 2 min |
| 4   | login.html, signup.html, dashboard shell, compose stub | Penke          | 2 min |
| 5   | Test suite results, coverage %                         | Jagadeesh      | 2 min |
| 6   | `summarize_text()` in REPL                             | Tummala        | 2 min |
| 7   | CI pipeline green                                      | Saniya / Kiran | 2 min |
| 8   | Q&A + feedback                                         | All            | 5 min |

---

## Sprint Retrospective Agenda (Friday 3:00 PM)

Each member answers:

1. What went well?
2. What slowed us down?
3. One thing to do differently in Sprint 2?

Action items → feed into Sprint 2 Planning.

---

## Definition of Done (DoD)

- [ ] Code pushed to `feature/*` branch, PR raised against `dev`.
- [ ] PR reviewed by at least one other member.
- [ ] New code has at least one corresponding test.
- [ ] All existing tests pass before PR merge.
- [ ] CI pipeline stays green after merge.
- [ ] No hardcoded secrets or API keys.
- [ ] No `print()` debug statements – use `logging`.

---

## Sprint 1 Acceptance Criteria

- [ ] `flask run` works on fresh clone + `.env` setup.
- [ ] `GET /health` → `200 {"status":"ok"}`.
- [ ] `POST /auth/signup` creates user and sets session.
- [ ] `POST /auth/login` authenticates and sets session.
- [ ] `GET /auth/logout` clears session.
- [ ] `GET /auth/status` returns 401 (unauthenticated) or user info (200).
- [ ] `GET /dashboard` redirects to login when no session.
- [ ] All 5 tables exist after `init_db()`.
- [ ] `nlp_service.summarize_text()` and `suggest_replies()` return stub output.
- [ ] `voice.transcribe_audio()` returns dict with `text`, `language`, `segments`.
- [ ] All tests pass in GitHub Actions CI.
- [ ] Coverage baseline ≥50% established.

---

## Known Risks & Mitigations

| Risk                             | Mitigation                                        |
| -------------------------------- | ------------------------------------------------- |
| Vivek overloaded                 | Dev tasks on Day 1 and Day 5 kept minimal         |
| Tummala overloaded (BE2 + AI/ML) | AI/ML tasks are stubs only in Sprint 1            |
| `models.py` merge conflicts      | Tummala owns `models.py`; Urmila only imports     |
| Whisper/torch slow CI install    | Mock model load in CI tests via `@patch`          |
| Jagadeesh context‑switching      | Testing tasks focus only on routes built that day |
| Saniya/Kiran coordination        | One person owns CI file; other reviews            |

---

## Tech Debt to Carry Into Sprint 2

- OAuth placeholders in login.html – Sprint 2
- Email route stubs – Sprint 2
- No rate limiting – Sprint 4
- No Alembic migrations – fix before production
- `summarize_text()` and `suggest_replies()` stubs – real implementation Sprint 2

---

## File Deliverables – Sprint 1 Exit
