# PLAN.md — Sprint 2 (Final Sprint)
## Voice-Based Email & Messaging Assistant

---

## Sprint Overview

| Field | Details |
|---|---|
| **Sprint Number** | Sprint 2 of 2 (Sprints 2–6 consolidated) |
| **Duration** | 5 working days (1 week) |
| **Scrum Master & Tech Lead** | Vivek Badodiya |
| **Sprint Goal** | Wire the redesigned frontend UI to real backend and AI functionality. Replace every mock/hardcoded value with live API data. Gmail OAuth, Telegram, voice dictation, TTS, AI search, and AI suggestions all working end-to-end. App deployable via Docker and live on Railway/Render. |
| **Status** | 🔄 Not Started |
| **Previous Sprint** | Sprint 1 ✅ COMPLETE |

---

## What Sprint 1 Delivered (Starting Point)

- ✅ GitHub repo, branch strategy, CI pipeline (GitHub Actions)
- ✅ Flask app factory, `/health` route
- ✅ SQLAlchemy + SQLite, all 5 DB tables: `users`, `user_tokens`, `email_messages`, `conversations`, `messages`
- ✅ Auth routes: POST `/auth/login`, `/auth/register`, GET `/auth/logout`, `/auth/status`, `/dashboard`
- ✅ bcrypt password hashing (`auth.py`)
- ✅ Stub routes: `/email/send`, `/email/list`, `/nlp/summarize`, `/nlp/suggest`, `/voice/transcribe`
- ✅ `nlp_service.py` stubs, `voice.py` stub
- ✅ Frontend templates: `base.html`, `login.html`, `signup.html`, `dashboard.html` shell, `compose.html` stub, `settings.html` stub, `error.html`
- ✅ JS modules: `api.js` (postJson), `app.js` (stub), `audio.js` (stub)
- ✅ Dockerfile scaffold

---

## What Sprint 2 Must Deliver

- Real Gmail OAuth 2.0 connect/disconnect
- Real message list + detail from Gmail API
- Dashboard stats from `/api/stats`
- AI inbox search, AI summary, AI reply suggestions (real NLP inference)
- Voice dictation in compose (Whisper)
- Read aloud in message view (gTTS)
- Compose send + save draft wired to real API
- Telegram webhook live
- All settings panels (Profile, Voice, Channels, Appearance) wired to real APIs
- Production Docker build + deployment on Railway/Render
- 80% test coverage
- README with screenshots + CONTRIBUTING.md

---

## Team & Roles

| Member | Role | Sprint 2 Focus |
|---|---|---|
| **Vivek Badodiya** | Scrum Master + Tech Lead | Gmail OAuth, channel routes, code reviews, integration, deployment coordination |
| Urmila Uttam Barkade | Backend Developer 1 | Message APIs, stats, send/draft, settings profile/notifications, rate limiting |
| Tummala Narasimhulu | Backend Dev 2 + AI/ML | TTS endpoint, NLP routes (summary, suggestions, search, draft), voice status |
| Penke Durga Prasad | Frontend Developer 1 | Dashboard wiring, message view, compose wiring, settings panels |
| Jagadeesh | Frontend Dev 2 + Testing Lead | Nav/sidebar wiring, AI search panel, tests, coverage, Sprint Review prep |
| Saniya Sulthana / Kiran | DevOps Engineer | CI updates, Docker, docker-compose, production deployment, monitoring |

> **Pace note:** Keeping to the same density as Sprint 1 actuals — 2–3 focused tasks per member per day. Tummala's AI/ML tasks are primarily route wrappers over existing stubs rather than net-new ML work.

---

## Sprint Ceremonies

| Ceremony | When | Duration | Owner |
|---|---|---|---|
| Sprint Planning | Day 1 Monday — 9:00 AM | 1.5 hours | Vivek |
| Daily Stand-up | Every day — 9:30 AM | 15 minutes | Vivek (facilitates) |
| Mid-sprint check | Day 3 Wednesday stand-up | 30 minutes | Vivek — compare progress vs acceptance criteria |
| Sprint Review | Day 5 Friday — 2:00 PM | 45 minutes | Vivek |
| Sprint Retrospective | Day 5 Friday — 3:00 PM | 30 minutes | Vivek |

---

## Sprint Backlog

---

### Day 1 — Monday
*Gmail OAuth live. Real message list in dashboard. Stats cards wired. AI summary endpoint.*

| Member | Tasks |
|---|---|
| **Vivek** | Facilitate Sprint Planning (1.5h). Implement Gmail OAuth: `gmail_service.get_authorization_url()`, `/auth/login-oauth` route, `/auth/google/callback` (exchange code → store token in `user_tokens`). Register `POST /api/channels/gmail/connect` and `DELETE /api/channels/gmail`. |
| **Urmila** | Implement `GET /api/messages` (paginated, supports `?folder=`, `?channel=`, `?label=`, `?sort=`, `?limit=`, `?offset=`) — pull from Gmail API via `email_service.list_emails()`. Implement `GET /api/stats` returning `{total_messages, unread_count, sent_today, ai_replies, trends}`. |
| **Tummala (BE2)** | Implement `GET /api/messages/<id>` returning full Gmail message body + metadata (sender, to, subject, timestamp, channel). Add DB index on `user_id` FK columns in `email_messages` and `user_tokens`. |
| **Penke** | Wire `dashboard.html` stats cards: replace hardcoded values (248, 12, 7, 31) with live fetch from `GET /api/stats` on page load. Wire message list: replace static HTML with rendered rows from `GET /api/messages` response. Add section headers (Today / Yesterday) generated from timestamps. |
| **Jagadeesh** | Update `base.html` nav avatar `#nav-avatar` to show real user initials from `GET /api/user/profile`. Wire `#inbox-badge` and `#draft-badge` to stats response. Write integration tests for `GET /api/messages` and `GET /api/stats`. |
| **Tummala (AI/ML)** | Implement `GET /api/summary/<id>`: fetch message body from DB/Gmail, call `nlp_service.summarize_text()`, return `{summary, sender}`. Add model warm-up call on app startup (dummy generate to eliminate cold-start latency). |
| **Saniya / Kiran** | Update CI `.github/workflows/python-app.yml`: mock Gmail API responses using `responses` library, mock `nlp_service.pipeline` with `@patch`, add `WHISPER_MODEL=tiny` env var. Confirm pipeline green. |

---

### Day 2 — Tuesday
*Message view wired. Compose send + draft live. AI search panel real. Reply suggestions live.*

| Member | Tasks |
|---|---|
| **Vivek** | Implement `POST /api/messages/mark-all-read` (mark all as read, refresh badge). Implement `POST /api/messages/<id>/archive` and `DELETE /api/messages/<id>`. Review and merge all Day 1 PRs into `dev`. |
| **Urmila** | Implement `POST /api/send`: accept `{to, subject, body, channel, scheduled_at}`, route to `email_service.send_email()` (Gmail) or `messaging_service.send_telegram_message()` (Telegram) based on `channel`. Implement `POST /api/drafts`. Add field validation (400 on missing required fields). |
| **Tummala (BE2)** | Implement `POST /api/ai/search`: accept `{query}`, search message subjects/bodies, return `{type: "text"|"results", content: string|[{id, sender, subject, snippet, channel, time}]}`. |
| **Penke** | Wire `message_view.html`: load full message from `GET /api/messages/<id>`, render AI summary from `GET /api/summary/<id>`, wire Reply/Forward buttons to `switchPage('compose', {to, subject, quoted_text})`, wire Archive/Delete buttons to API calls then `switchPage('dashboard')`. Sanitize HTML body before `innerHTML`. |
| **Jagadeesh** | Wire AI search panel in `dashboard.html`: replace mock `aiKnowledge` lookup with real `POST /api/ai/search` call in `sendAiQuery()`. Render result cards from `type:'results'` response. Wire result card click to `switchPage('message', {id})`. Write tests for AI search route. |
| **Tummala (AI/ML)** | Implement `GET /api/suggestions/<id>`: call `nlp_service.suggest_replies()` on message body, return `{suggestions: [str, str, str]}`. Implement `POST /api/ai/generate-draft`: accept `{context: {to, subject}}`, call `nlp_service.generate_draft()`, return `{draft: str}`. |
| **Saniya / Kiran** | Add GitHub Actions step: build Docker image and run full test suite inside container (`docker build && docker run pytest`). Fix any container-specific failures (missing system libs, path issues). |

---

### Day 3 — Wednesday
*Voice features live. Telegram wired. Settings backend.*
*(Mid-sprint check during stand-up — Vivek reviews progress vs acceptance criteria)*

| Member | Tasks |
|---|---|
| **Vivek** | Implement Telegram in `telegram_routes.py`: `POST /webhook/telegram` receives updates, saves to `messages` table, sends bot reply via `messaging_service`. Register `POST /api/channels/telegram/connect` (save bot token to `user_tokens`). |
| **Urmila** | Implement `GET /api/user/profile` and `PUT /api/user/profile` (name, email, phone, timezone). Implement `POST /api/user/avatar` (file upload). Implement `POST /auth/change-password` (verify old password, hash new, save). Implement `PUT /api/settings/notif`. |
| **Tummala (BE2)** | Implement `POST /api/tts`: accept `{text, speed}`, call `voice.speak_text(text, speed=speed)`, return MP3 file as response with `Content-Type: audio/mpeg`. Implement `GET /api/voice/status`: return `{status: "online"|"offline", model: "whisper-tiny"}`. |
| **Penke** | Wire `compose.html`: channel dropdown updates To field placeholder + hides/shows subject field via JS. Wire Send button to `POST /api/send` via `apiRequest()`. Wire Save Draft to `POST /api/drafts`. Wire `✦ AI Write` button to `POST /api/ai/generate-draft` — insert returned draft into textarea. |
| **Jagadeesh** | Wire `message_view.html` Read aloud button: call `POST /api/tts {text, speed}` via `audio.js`, play returned audio via `AudioContext` or `<audio>` element. Wire Suggested Replies chips: render from `GET /api/suggestions/<id>`, Use button → `switchPage('compose', {body: suggestion, to, subject})`. Write end-to-end test for compose flow. |
| **Tummala (AI/ML)** | Add voice dictation microphone button to `compose.html` (next to `✦ AI Write`). Implement in `audio.js`: `getUserMedia` → `MediaRecorder` → blob on stop → `POST /api/voice/transcribe` (multipart/form-data) → append returned text to message textarea. Add waveform canvas visualiser using `AnalyserNode` during recording. |
| **Saniya / Kiran** | Create `docker-compose.yaml`: `web` service (build from Dockerfile, env_file: .env) + volume for Whisper/HuggingFace model cache. Verify `docker-compose up` starts app locally without errors. |

---

### Day 4 — Thursday
*Settings UI fully wired. Performance + logging. Production deployed.*

| Member | Tasks |
|---|---|
| **Vivek** | Wire `settings.html` Channels panel: Connect Gmail button → `/auth/login-oauth?next=settings`, Disconnect Gmail → `DELETE /api/channels/gmail`. Connect Telegram section → token input form → `POST /api/channels/telegram/connect`. Code review all Day 3 PRs, merge into `dev`. |
| **Urmila** | Implement `PUT /api/settings/voice` (store auto-reply, tone, auto-summarise, speed in `user_tokens` or new settings column). Add Flask-Limiter rate limiting: 10 req/min on `/api/voice/transcribe` and `/api/tts`, 20 req/min on NLP endpoints. |
| **Tummala (BE2)** | Add structured logging via Python `logging` module to all service functions (INFO for success, ERROR for exceptions, WARNING for slow calls >5s). Add `request_id` header to all responses. Gmail token auto-refresh: catch expired token, call `gmail_service.refresh_token()`, retry API call. |
| **Penke** | Wire `settings.html` Profile panel to `GET / PUT /api/user/profile` — load values on panel open, save on Submit. Wire Voice panel to `PUT /api/settings/voice`. Wire Appearance panel: theme toggle (add/remove `.dark-mode` class on `<body>`, persist in `localStorage`), density + font size via CSS class on body (also `localStorage`). |
| **Jagadeesh** | Wire all 6 settings panels via `switchSettingsNav()` — verify correct panel shows/hides for each sidebar item. Wire Sign Out in settings sidebar to `handleLogout()`. Write tests for settings API endpoints. Run coverage check — identify gaps, write missing tests to reach 80%. |
| **Tummala (AI/ML)** | Add VA status polling in sidebar: `setInterval(() => getJson('/api/voice/status'), 30000)` — update `#va-status-text` dot colour (green = online, red = offline) and text. Add voice login button stub on login screen (calls `goToApp()` for now — full implementation future sprint). |
| **Saniya / Kiran** | Deploy to Railway (or Render): connect GitHub `main` branch, configure all env vars in platform dashboard, update `GOOGLE_OAUTH_REDIRECT_URI` to production URL, update Google Cloud OAuth allowed redirect URIs. Register Telegram webhook to production URL via `setWebhook` API. |

---

### Day 5 — Friday
*Integration. Bug fixes. Security. Sprint Review. Retro.*

| Member | Tasks |
|---|---|
| **Vivek** | Merge all Day 4 PRs into `dev`. Fix any P1 integration bugs. Security audit: HTTPS enforced, no secrets in repo, correct CORS headers, `SECRET_KEY` not default. Add MIT licence file. Facilitate Sprint Review (45 min) + Retrospective (30 min). |
| **Urmila** | Fix any auth edge cases from integration: Gmail token expiry redirect, login error messages match new split-panel UI tabs (Sign In / Register). Ensure `/auth/register` is aligned with new frontend (`registerAndLogin()` → real POST). |
| **Tummala (BE2)** | Run `bandit -r src/` and `pip-audit` on `requirements.txt`. Fix any high-severity findings. Verify all 5 tables stable in production DB. Document inference benchmarks (model load time, summarize time, transcribe time) in `docs/ARCHITECTURE.md`. |
| **Penke** | Final UI polish: loading spinners on all async fetch calls, skeleton loaders for message list rows while loading, mobile responsive pass (single column layout below 768px for all pages). Take screenshots of all pages for `README.md`. |
| **Jagadeesh** | Run full test suite on merged `dev` branch. Confirm zero failures. Generate HTML coverage report (`pytest --cov=src --cov-report=html`). Confirm coverage ≥ 80%. Prepare Sprint Review test summary (total tests, pass rate, coverage %, known issues). |
| **Tummala (AI/ML)** | Verify all AI/ML endpoints respond correctly in production. Check model cold-start time. Confirm voice dictation and TTS work in production HTTPS environment (MediaRecorder requires HTTPS — won't work over plain HTTP). |
| **Saniya / Kiran** | Add CD: GitHub Actions step to auto-deploy to Railway on merge to `main`. Enable GitHub Dependabot + CodeQL scanning. Add branch protection rules on `main` (require PR + CI green before merge). Set up UptimeRobot free tier monitoring on `/health`. Final CI run — must be green. |

---

## Sprint Review Agenda (Friday 2:00 PM)
*Facilitated by Vivek*

| # | Demo | Owner | Time |
|---|---|---|---|
| 1 | Sprint goal recap | Vivek | 2 min |
| 2 | Login → register → dashboard with real Gmail inbox | Urmila | 3 min |
| 3 | Click message → view page → AI summary → read aloud | Penke | 3 min |
| 4 | Compose → voice dictate → AI Write → send email | Penke | 3 min |
| 5 | Dashboard AI search → real results → open message | Jagadeesh | 2 min |
| 6 | Settings: connect Gmail, save profile, theme toggle | Jagadeesh | 2 min |
| 7 | Production URL live on Railway/Render | Saniya/Kiran | 2 min |
| 8 | CI green, 80% coverage | Jagadeesh | 2 min |
| 9 | Q&A + final feedback | All | 5 min |

---

## Sprint Retrospective Agenda (Friday 3:00 PM)
*Facilitated by Vivek — blameless format*

Each member answers:
1. **What went well across both sprints?**
2. **What slowed us down most?**
3. **What would we do differently if starting again?**
4. **What should go in the future backlog?** (WhatsApp, admin dashboard, Electron app)

Action items captured → added to project `README.md` Future Enhancements section.

---

## Definition of Done (DoD)

- [ ] Code pushed to `feature/*` branch, PR raised targeting `dev`
- [ ] PR reviewed and approved by at least one other member (Vivek for backend core)
- [ ] New code has corresponding unit or integration tests
- [ ] All existing tests pass before PR is raised
- [ ] CI pipeline stays green after merge
- [ ] **No hardcoded mock data** — all UI values come from real API responses
- [ ] No secrets, credentials, or `print()` debug statements in committed code
- [ ] API endpoint responds with correct HTTP status and JSON shape

---

## Sprint 2 Acceptance Criteria

The sprint is **complete** when all of the following pass:

- [ ] `POST /auth/login` and `POST /auth/register` work with new split-panel UI (Sign In / Register tabs)
- [ ] Google OAuth `Continue with Google` connects Gmail and redirects back to settings
- [ ] Dashboard message list shows real Gmail inbox (no hardcoded HTML rows)
- [ ] Dashboard stats cards show real values from `GET /api/stats`
- [ ] AI search panel calls `POST /api/ai/search` and renders result cards
- [ ] Message view shows real message body + AI summary from `GET /api/summary/<id>`
- [ ] Read aloud button plays TTS audio from `POST /api/tts`
- [ ] Suggested replies rendered from `GET /api/suggestions/<id>`, Use button pre-fills compose
- [ ] Compose: Send button calls `POST /api/send`, success toast shown
- [ ] Compose: Voice dictation records → transcribes → appends to textarea
- [ ] Compose: `✦ AI Write` button inserts generated draft text
- [ ] Settings Profile panel loads from and saves to `GET / PUT /api/user/profile`
- [ ] Settings Channels panel shows Gmail/Telegram connect/disconnect working
- [ ] Settings Appearance panel theme toggle persists in localStorage
- [ ] App runs via `docker-compose up` without errors
- [ ] App is live on production URL with HTTPS
- [ ] All tests pass in GitHub Actions CI — zero failures
- [ ] Coverage ≥ 80%
- [ ] No P1 bugs open at end of sprint

---

## Known Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Vivek overloaded (SM + TL + OAuth) | High | High | OAuth is Vivek's primary feature — all other BE routes owned by Urmila |
| Tummala dual-role bottleneck (BE2 + AI/ML) | High | Medium | AI tasks are route wrappers over existing stubs — not new model training |
| Gmail API quota in dev | Medium | Medium | Dedicated test Gmail account, mock in unit tests, cache responses |
| HuggingFace model timeout in CI | High | Medium | `@patch nlp_service.pipeline` in all CI tests, `WHISPER_MODEL=tiny` |
| Telegram needs public URL for webhook | High | Low | ngrok locally, production URL Day 4 |
| MediaRecorder requires HTTPS for voice | Medium | Medium | Voice dictation tested last on production — won't work on localhost HTTP |
| `models.py` merge conflicts | Medium | Low | Tummala owns `models.py`, all others import only |
| Railway/Render cold start slow (model load) | Medium | Low | Model warm-up on startup — document first-request latency in README |

---

## Tech Debt from Sprint 1 — Resolved This Sprint

| Item | Day | Owner |
|---|---|---|
| Gmail OAuth placeholder buttons not wired | Day 1 | Vivek |
| Email route stubs return `{}` hardcoded | Day 1–2 | Urmila |
| `nlp_service.py` stubs (no real inference) | Day 1 | Tummala |
| No rate limiting | Day 4 | Urmila |
| No structured logging | Day 4 | Tummala |
| No Docker / docker-compose | Day 3–4 | Saniya/Kiran |

## Remaining Tech Debt (future v2.0)

- No Alembic migrations — `init_db()` used throughout dev
- WhatsApp integration (Cloud API) — not in scope for Sprint 2
- Voice login (`/auth/voice-login`) — stub only, full implementation future
- Admin dashboard — future
- Electron desktop wrapper — future

---

## File Deliverables — Sprint 2 Exit

```
src/
├── app.py                     ✅ All /api/* routes registered
├── models.py                  ✅ Stable — no changes from Sprint 1
└── services/
    ├── auth.py                ✅ register_token() fully working
    ├── gmail_service.py       ✅ OAuth flow, token exchange
    ├── email_service.py       ✅ list_emails(), read_email(), send_email() — real Gmail
    ├── messaging_service.py   ✅ send_telegram_message() with user token
    ├── nlp_service.py         ✅ summarize, suggest, generate_draft, search — real inference
    └── voice.py               ✅ transcribe_audio() + speak_text() — real Whisper + gTTS
src/web/
├── auth_routes.py             ✅ All auth + settings + channel routes
└── telegram_routes.py         ✅ Webhook handler, message save, bot reply
templates/
├── base.html                  ✅ Real user data in nav, VA status polling
├── login.html                 ✅ Real POST /auth/login and /auth/register wired
├── dashboard.html             ✅ Real stats + message list + AI search wired
├── message_view.html          ✅ Real data, AI summary, TTS, suggestions
├── compose.html               ✅ Send, draft, AI Write, voice dictation all wired
└── settings.html              ✅ All 6 panels wired to real APIs
static/js/
├── api.js                     ✅ apiRequest() + getJson() + postJson()
├── app.js                     ✅ SPA router + all UI functions
└── audio.js                   ✅ Voice dictation + TTS playback + waveform
Dockerfile                     ✅ Production-ready (gunicorn, python:3.11-slim)
docker-compose.yaml            ✅ Web + model cache volume
README.md                      ✅ Screenshots, quick start, env vars, CI badge
CONTRIBUTING.md                ✅ Branch strategy, PR template, coding standards
docs/ARCHITECTURE.md           ✅ Updated with Sprint 2 decisions + benchmarks
docs/DEPLOYMENT.md             ✅ Full Railway/Render production setup guide
```

---

*Sprint 2 of 2 (Final Sprint) — Voice-Based Email & Messaging Assistant*
*Vivek Badodiya — Scrum Master & Tech Lead*
*Team: Urmila · Tummala · Penke · Jagadeesh · Saniya / Kiran*
*5-day sprint · Agile Scrum · Sprints 2–6 consolidated*
