# PLAN.md — Sprint 2 (Final Sprint)

## Voice-Based Email & Messaging Assistant

---

## Sprint Overview

| Field                        | Details                                                                                                                                                                                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Sprint Number**            | Sprint 2 of 2                                                                                                                                                                                                                            |
| **Duration**                 | 5 working days (1 week)                                                                                                                                                                                                                  |
| **Scrum Master & Tech Lead** | Vivek Badodiya                                                                                                                                                                                                                           |
| **Sprint Goal**              | Wire all frontend screens to real backend APIs. Replace every hardcoded/mock value with live data. Gmail OAuth, Telegram, voice dictation, TTS, AI search, and AI suggestions working end-to-end. App live on Railway/Render via Docker. |
| **Status**                   | 🔄 Not Started                                                                                                                                                                                                                           |
| **Previous Sprint**          | Sprint 1 ✅ COMPLETE                                                                                                                                                                                                                     |

---

## Team & Roles

| Member               | Role                              |
| -------------------- | --------------------------------- |
| Vivek Badodiya       | Scrum Master + Tech Lead          |
| Urmila Uttam Barkade | Backend Developer                 |
| Tummala              | AI / ML Engineer                  |
| Penke Durga Prasad   | Frontend Developer                |
| Jagadeesh            | Frontend Developer + Testing Lead |
| Saniya / Kiran       | DevOps Engineer                   |

---

## Sprint Ceremonies

| Ceremony         | When                | Duration |
| ---------------- | ------------------- | -------- |
| Sprint Planning  | Day 1 — 9:00 AM     | 1.5 hrs  |
| Daily Stand-up   | Every day — 9:30 AM | 15 min   |
| Mid-Sprint Check | Day 3 — stand-up    | 30 min   |
| Sprint Review    | Day 5 — 2:00 PM     | 45 min   |
| Retrospective    | Day 5 — 3:00 PM     | 30 min   |

---

## Folder-Based Task Ownership

Tasks are grouped by folder/module. Each member owns specific folders across the sprint.

---

### `src/services/` — Backend Services

**Owner: Vivek**

| Day   | Task                                                                      |
| ----- | ------------------------------------------------------------------------- |
| Day 1 | `gmail_service.py` — OAuth flow: get auth URL, exchange code, store token |
| Day 2 | `gmail_service.py` — token auto-refresh on expiry                         |
| Day 3 | `messaging_service.py` — Telegram: send message with user bot token       |
| Day 4 | Add structured logging (INFO / ERROR / WARNING) across all service files  |
| Day 5 | Security audit — run `bandit` + `pip-audit`, fix high-severity findings   |

---

**Owner: Urmila**

| Day   | Task                                                                                      |
| ----- | ----------------------------------------------------------------------------------------- |
| Day 1 | `email_service.py` — `list_emails()` with pagination and filters (folder, channel, label) |
| Day 2 | `email_service.py` — `send_email()`, `save_draft()` with field validation                 |
| Day 3 | `auth.py` — `change_password()`, `update_profile()`, `upload_avatar()`                    |
| Day 4 | `email_service.py` — rate limiting on voice/NLP endpoints via Flask-Limiter               |
| Day 5 | Fix auth edge cases: Gmail token expiry redirect, register/login error alignment          |

---

**Owner: Tummala**

| Day   | Task                                                                    |
| ----- | ----------------------------------------------------------------------- |
| Day 1 | `nlp_service.py` — `summarize_text()` with model warm-up on app startup |
| Day 2 | `nlp_service.py` — `suggest_replies()`, `generate_draft()`              |
| Day 3 | `voice.py` — `transcribe_audio()` (Whisper) + `speak_text()` (gTTS)     |
| Day 4 | `nlp_service.py` — `search_messages()` for AI inbox search              |
| Day 5 | Verify all AI/ML endpoints in production; document inference benchmarks |

---

### `src/web/` — Route Files

**Owner: Vivek**

| Day   | Task                                                                                                                              |
| ----- | --------------------------------------------------------------------------------------------------------------------------------- |
| Day 1 | `auth_routes.py` — `/auth/login-oauth`, `/auth/google/callback`, `POST /api/channels/gmail/connect`, `DELETE /api/channels/gmail` |
| Day 2 | `auth_routes.py` — `POST /api/messages/mark-all-read`, `POST /api/messages/<id>/archive`, `DELETE /api/messages/<id>`             |
| Day 3 | `telegram_routes.py` — `POST /webhook/telegram`, `POST /api/channels/telegram/connect`                                            |
| Day 4 | Review + merge all Day 3 PRs into `dev`; wire settings channel connect/disconnect                                                 |
| Day 5 | Merge all Day 4 PRs; fix P1 integration bugs; add MIT licence                                                                     |

---

**Owner: Urmila**

| Day   | Task                                                                                               |
| ----- | -------------------------------------------------------------------------------------------------- |
| Day 1 | `auth_routes.py` — `GET /api/messages` (paginated), `GET /api/stats`                               |
| Day 2 | `auth_routes.py` — `POST /api/send`, `POST /api/drafts`                                            |
| Day 3 | `auth_routes.py` — `GET/PUT /api/user/profile`, `POST /api/user/avatar`, `PUT /api/settings/notif` |
| Day 4 | `auth_routes.py` — `PUT /api/settings/voice`                                                       |
| Day 5 | Verify all auth routes stable end-to-end in production                                             |

---

**Owner: Tummala**

| Day   | Task                                                                                                   |
| ----- | ------------------------------------------------------------------------------------------------------ |
| Day 1 | `auth_routes.py` — `GET /api/messages/<id>` with full message body + metadata                          |
| Day 2 | `auth_routes.py` — `POST /api/ai/search`                                                               |
| Day 3 | `auth_routes.py` — `POST /api/tts`, `GET /api/voice/status`                                            |
| Day 4 | `auth_routes.py` — `GET /api/summary/<id>`, `GET /api/suggestions/<id>`, `POST /api/ai/generate-draft` |
| Day 5 | Confirm voice + TTS work over HTTPS in production (MediaRecorder requires HTTPS)                       |

---

### `templates/` — HTML Templates

**Owner: Penke**

| Day   | Task                                                                                                                                       |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Day 1 | `dashboard.html` — wire stats cards to `GET /api/stats`; wire message list to `GET /api/messages` with Today/Yesterday headers             |
| Day 2 | `message_view.html` — load message body, AI summary, wire Reply/Forward/Archive/Delete                                                     |
| Day 3 | `compose.html` — wire Send, Save Draft, AI Write button; channel dropdown behaviour                                                        |
| Day 4 | `settings.html` — wire Profile panel (`GET/PUT /api/user/profile`), Voice panel, Appearance panel (theme + density + font, `localStorage`) |
| Day 5 | UI polish — loading spinners, skeleton loaders, mobile responsive pass (≤768px); screenshots for README                                    |

---

**Owner: Jagadeesh**

| Day   | Task                                                                                                        |
| ----- | ----------------------------------------------------------------------------------------------------------- |
| Day 1 | `base.html` — wire `#nav-avatar` initials, `#inbox-badge`, `#draft-badge` to live API data                  |
| Day 2 | `dashboard.html` — wire AI search panel to `POST /api/ai/search`; render result cards; click → message view |
| Day 3 | `message_view.html` — wire Read Aloud button to `POST /api/tts`; wire Suggested Replies chips to compose    |
| Day 4 | `settings.html` — wire all 6 settings panels via `switchSettingsNav()`; wire Sign Out to `handleLogout()`   |
| Day 5 | Final test run on merged `dev`; generate coverage HTML report; prepare Sprint Review summary                |

---

### `static/js/` — JavaScript Modules

**Owner: Penke**

| Day   | Task                                                                           |
| ----- | ------------------------------------------------------------------------------ |
| Day 2 | `app.js` — `switchPage()` SPA router; message view rendering from API response |
| Day 3 | `app.js` — compose page wiring; `updateCounter()`; AI Write integration        |
| Day 4 | `app.js` — settings panel wiring; theme toggle via CSS class on `<body>`       |

---

**Owner: Jagadeesh**

| Day   | Task                                                                                         |
| ----- | -------------------------------------------------------------------------------------------- |
| Day 1 | `api.js` — `apiRequest()`, `getJson()`, `postJson()` wrappers with auth token + error toasts |
| Day 2 | `app.js` — `sendAiQuery()` wired to real API; result card rendering                          |
| Day 3 | `audio.js` — `playTTS()`: fetch audio from `/api/tts`, play via `<audio>` element            |
| Day 4 | `app.js` — `switchSettingsNav()`, `handleNavSearch()`, `handleLogout()` all wired            |

---

**Owner: Tummala**

| Day   | Task                                                                                                                                    |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Day 3 | `audio.js` — `startDictation()`: `getUserMedia` → `MediaRecorder` → `POST /api/voice/transcribe` → insert text; add waveform visualiser |
| Day 4 | `app.js` — VA status polling every 30s (`GET /api/voice/status`); update `#va-status-text` dot colour                                   |

---

### `tests/` — Test Files

**Owner: Jagadeesh**

| Day   | Task                                                                          |
| ----- | ----------------------------------------------------------------------------- |
| Day 1 | Tests for `GET /api/messages` and `GET /api/stats`                            |
| Day 2 | Tests for AI search route (`POST /api/ai/search`)                             |
| Day 3 | End-to-end test for compose flow (send + draft)                               |
| Day 4 | Tests for settings API endpoints; run coverage check; fill gaps to reach 80%  |
| Day 5 | Full suite run on merged `dev`; confirm zero failures; confirm coverage ≥ 80% |

---

**Owner: Saniya / Kiran**

| Day   | Task                                                                                                                     |
| ----- | ------------------------------------------------------------------------------------------------------------------------ |
| Day 1 | Update CI — mock Gmail API with `responses` library; mock `nlp_service.pipeline` with `@patch`; set `WHISPER_MODEL=tiny` |
| Day 2 | Add CI step: build Docker image + run `pytest` inside container                                                          |
| Day 4 | Add CD step: auto-deploy to Railway on merge to `main`                                                                   |
| Day 5 | Enable Dependabot + CodeQL; add branch protection on `main`; final CI run must be green                                  |

---

### `Dockerfile` + `docker-compose.yaml` — Containerisation

**Owner: Saniya / Kiran**

| Day   | Task                                                                                                                      |
| ----- | ------------------------------------------------------------------------------------------------------------------------- |
| Day 3 | `docker-compose.yaml` — `web` service with env_file + model cache volume; verify `docker-compose up` runs locally         |
| Day 4 | Deploy to Railway/Render — configure all env vars, update OAuth redirect URI, register Telegram webhook to production URL |
| Day 5 | Set up UptimeRobot monitoring on `/health` endpoint                                                                       |

---

### `docs/` + Root Files — Documentation

**Owner: Vivek**

| Day   | Task                                                                                                       |
| ----- | ---------------------------------------------------------------------------------------------------------- |
| Day 5 | `docs/ARCHITECTURE.md` — update with Sprint 2 decisions; `CONTRIBUTING.md` — branch strategy + PR template |

**Owner: Tummala**

| Day   | Task                                                                                        |
| ----- | ------------------------------------------------------------------------------------------- |
| Day 5 | `docs/ARCHITECTURE.md` — add inference benchmarks (model load, summarize, transcribe times) |

**Owner: Penke**

| Day   | Task                                                                        |
| ----- | --------------------------------------------------------------------------- |
| Day 5 | `README.md` — add screenshots of all pages, quick start, env vars, CI badge |

**Owner: Saniya / Kiran**

| Day     | Task                                                              |
| ------- | ----------------------------------------------------------------- |
| Day 4–5 | `docs/DEPLOYMENT.md` — full Railway/Render production setup guide |

---

## Definition of Done

- [ ] Code pushed to `feature/*` branch, PR raised targeting `dev`
- [ ] PR reviewed by at least one other member
- [ ] New code has corresponding unit or integration tests
- [ ] All existing tests pass before PR is raised
- [ ] CI pipeline stays green after merge
- [ ] No hardcoded mock data — all UI values from real API responses
- [ ] No secrets, credentials, or `print()` debug statements committed
- [ ] API endpoint returns correct HTTP status and JSON shape

---

## Sprint 2 Acceptance Criteria

- [ ] Login and register work with split-panel UI (Sign In / Register tabs)
- [ ] Google OAuth connects Gmail and redirects back to settings
- [ ] Dashboard shows real Gmail message list and live stats cards
- [ ] AI search panel calls `POST /api/ai/search` and renders result cards
- [ ] Message view shows real body + AI summary + TTS read aloud
- [ ] Suggested replies render and pre-fill compose on "Use"
- [ ] Compose: Send, Save Draft, AI Write, and Voice Dictation all working
- [ ] Settings: Profile, Voice, Channels, Appearance panels all wired to real APIs
- [ ] Theme toggle persists in `localStorage`
- [ ] App runs via `docker-compose up` without errors
- [ ] App is live on production URL with HTTPS
- [ ] All tests pass in GitHub Actions CI — zero failures
- [ ] Coverage ≥ 80%
- [ ] No P1 bugs open at end of sprint

---

## Known Risks

| Risk                               | Mitigation                                                            |
| ---------------------------------- | --------------------------------------------------------------------- |
| Vivek overloaded (SM + TL + OAuth) | OAuth is Vivek's primary feature; all other BE routes owned by Urmila |
| Gmail API quota in dev             | Use a test Gmail account; mock in all unit tests                      |
| HuggingFace model timeout in CI    | Patch `nlp_service.pipeline` in CI; use `WHISPER_MODEL=tiny`          |
| Telegram webhook needs public URL  | Use ngrok locally; production URL available Day 4                     |
| Voice dictation requires HTTPS     | Test voice features last, on production only                          |
| `models.py` merge conflicts        | Tummala owns `models.py`; all others import only                      |

---

## Remaining Tech Debt (v2.0)

- No Alembic migrations — `init_db()` used throughout
- WhatsApp integration — not in scope
- Voice login — stub only, full implementation future sprint
- Admin dashboard — future
- Electron desktop wrapper — future

---

_Sprint 2 of 2 — Voice-Based Email & Messaging Assistant_
_Vivek Badodiya — Scrum Master & Tech Lead_
_Team: Urmila · Tummala · Penke · Jagadeesh · Saniya / Kiran_
