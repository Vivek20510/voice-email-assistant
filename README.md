# 🎙️ Voice-Based Email & Messaging Assistant

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Framework](https://img.shields.io/badge/Flask-2.3+-black?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![AI Engine](https://img.shields.io/badge/AI%20%2F%20ML-PyTorch%20%7C%20HuggingFace%20%7C%20Whisper-orange?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)

An elegant, premium-grade AI-powered dashboard that consolidates **Gmail**, **Outlook**, and **Telegram** into a unified, voice-controlled communications hub. Users can manage their inboxes hands-free through state-of-the-art voice dictation, text-to-speech audio playbacks, automated smart AI suggestions, multi-lingual translations, and deep message summarization.

Designed with a stunning responsive layout, fluid CSS micro-animations, theme persistence, and modular services, this application represents the modern standard for accessibility-first messaging utilities.

---

## 🌟 Core Highlights

### 1. 🎙️ Voice-Command & Dictation Console
*   **Speech-to-Text (STT):** Dictate compose forms and replies directly via your browser. Integrated with **OpenAI Whisper** for high-accuracy local transcription, accompanied by a dynamic, real-time CSS waveform visualizer.
*   **Text-to-Speech (TTS):** Read messages aloud at the click of a button using Google's Text-to-Speech (**gTTS**) system, keeping you informed on the go.

### 2. 🤖 Deep AI Inbox Assistant
*   **Smart Drafting:** Draft professional replies instantly. The platform leverages a local **Qwen-2.5 (1.5B/7B)** or HuggingFace API instruction model to generate structured drafts based on short voice hints.
*   **Thread Summarizer:** Transform long email threads or chat history into concise, readable summaries via fine-tuned **BART/T5** pipeline inference.
*   **Suggested Reply Chips:** Read a message and instantly pick from dynamically generated smart action buttons (e.g., *Accept Invite*, *Ask for details*, *Polite Decline*) that automatically pre-fill your composer.
*   **Multilingual Translations:** Read and reply across barriers using integrated **mBART-50** and **NLLB** models, enabling many-to-many instant translations.

### 3. 🔄 Multi-Channel Sync
*   **Google OAuth & Gmail API:** Fully authenticated secure OAuth 2.0 flow. Synchronize real-time Gmail inbox folders, read messages, compose drafts, and send mail securely.
*   **Microsoft Outlook Integration:** Direct API interface for fetching and dispatching Outlook mail.
*   **Telegram Webhooks:** Connect custom Telegram bots to monitor incoming messages and reply directly from the centralized application dashboard.

### 4. 🎨 Sleek, Responsive Interface
*   **Dynamic Theme Toggle:** Instantly switch between premium, harmonious Dark Mode and Light Mode with settings persisted across sessions in `localStorage`.
*   **Glassmorphism Panels:** Modern, translucent card aesthetics with sophisticated layout densities and smooth micro-animations.
*   **Fluid SPA Router:** Zero-latency Single Page Application feel, built with Vanilla JavaScript and decoupled CSS modules.

---

## 📂 Project Directory Structure

```text
voice-email-assistant/
├── .env.example              # Schema template for environment variables and model locations
├── Dockerfile                # Multi-stage optimized Docker deployment specification
├── PLAN.md                   # Detailed project sprints, ceremony logs, and task assignments
├── requirements.txt          # Python application dependencies (Flask, PyTorch, Transformers, etc.)
├── run.py                    # Application launcher / Dev Server entrypoint
├── package.json              # Developer tools configuration (Prettier styling configs)
├── pytest.ini                # Pytest framework configurations
│
├── docs/                     # Architectural logs & deployment manuals
│   ├── ARCHITECTURE.md       # Deep-dive backend, service, and database blueprints
│   ├── DEPLOYMENT.md         # Production guidelines for Railway, Render, and Docker
│   ├── PROJECT_PROGRESS.md   # Sprint execution logs and velocity tracker
│   └── SETUP_GUIDE.md        # Beginner quickstart documentation
│
├── src/                      # Monolithic Python backend
│   ├── app.py                # Main Flask factory, blueprint registration, and config hooks
│   ├── db.py                 # SQLite SQLAlchemy database engine connector
│   │
│   ├── models/               # Database tables and entity mappings
│   │   └── __init__.py       # ORM Schema (Users, Messages, Preferences, OAuth tokens)
│   │
│   ├── services/             # Core Business Logic & AI Services
│   │   ├── __init__.py       # Service module initialization
│   │   ├── ai_service.py     # Base pipeline loaders for HuggingFace and local PyTorch engines
│   │   ├── auth.py           # Secure password hashing, login validations, and avatars
│   │   ├── email_service.py  # Internal inbox filters, message parsers, and dispatch engines
│   │   ├── nlp_service.py    # AI Vector search matching and search indexes
│   │   ├── outlook_service.py# REST API wrapper client for Microsoft Outlook
│   │   ├── preferences.py    # Controller actions for User preference panels
│   │   ├── qwen_draft_service.py # Qwen-based email/draft template generators
│   │   ├── qwen_reply_service.py # Intelligent suggested replies generator
│   │   ├── summary_service.py # Text summary engines using BART/T5 models
│   │   ├── translation.py    # Multi-lingual translations with mBART-50
│   │   └── voice.py          # Whisper transcription and gTTS vocal synthesis handlers
│   │
│   └── web/                  # API Routers / Web Controllers
│       ├── __init__.py       # Web module initialization
│       ├── ai_guard.py       # Middleware handler managing premium AI usage quotas
│       ├── ai_panel_routes.py# Route handlers for client sidebar AI interactions
│       ├── auth_routes.py    # Routing for logins, OAuth flow redirects, and registration
│       ├── compose_routes.py # Compose/Save draft and email dispatch endpoints
│       ├── email_routes.py   # Inbox list, individual message fetchers, and folder actions
│       ├── nlp_routes.py     # AI Vector search endpoints
│       ├── summary_routes.py # Thread summary triggers
│       ├── translation_routes.py # Translation engine triggers
│       └── voice_routes.py   # Audio audio upload, transcription, and TTS streams
│
├── static/                   # Static browser-facing client resources
│   ├── css/                  # Curated styling modules
│   │   ├── ai-panel.css      # Styling for collapsible AI sidebar utilities
│   │   ├── base.css          # Color tokens, CSS variables, and layout resets
│   │   ├── compose.css       # Audio Waveforms and email compose workspace styles
│   │   ├── dashboard.css     # Clean inbox, charts, stats grid, and mail folders
│   │   ├── error.css         # Minimalist error pages
│   │   ├── login.css         # Split-panel elegant authentication styles
│   │   ├── message_view.css  # Interactive thread, summary cards, and audio buttons
│   │   ├── settings.css      # Profile settings, channels sync panels, and sliders
│   │   └── style.css         # Global core stylesheets
│   │
│   └── js/                   # Frontend SPA JavaScript modules
│       ├── ai.js             # High-level AI helper functions
│       ├── ai_panel.js       # AI panel handlers and sidebar layout dynamics
│       ├── app.js            # Main Single Page App controller and routing setup
│       ├── compose.js        # Waveform recorder, dictation, and draft controllers
│       ├── dashboard.js      # Mail categorization, pagination, and AI search routines
│       ├── message.js        # Individual email interaction layer
│       ├── message_summary.js # Thread summary triggers and speech vocal controllers
│       └── settings.js       # Custom theme settings and channel sync selectors
│
├── templates/                # Jinja2 HTML core components
│   ├── ai_panel.html         # Sidebar component interface
│   ├── base.html             # Main dashboard framework shell
│   ├── compose.html          # Modular workspace for composing messages
│   ├── dashboard.html        # Message lists, counts, and quick filter categories
│   ├── error.html            # Error display layouts
│   ├── login.html            # User login prompt screen
│   ├── message_view.html     # Email details reader view
│   ├── settings.html         # Settings, theme, and profile panels
│   └── signup.html           # User onboarding form
│
└── tests/                    # Robust verification test suites
    ├── conftest.py           # Pytest configurations and dependency mocks
    ├── test_ai_panel_js.py   # JavaScript interface tests
    └── test_auth_phase1.py   # Complete user login and OAuth lifecycle tests
```

---

## 🛠️ Installation & Local Setup

Get your voice email assistant up and running in minutes.

### 📋 Prerequisites
Ensure you have the following installed on your machine:
*   **Python:** Version `3.10` or `3.11`
*   **FFmpeg:** Required for processing recorded audio formats (Whisper processing)
*   *(Optional)* **Docker Desktop:** For simple, containerized execution

### 🚀 Standard Setup
1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Vivek20510/voice-email-assistant.git
    cd voice-email-assistant
    ```

2.  **Create & Activate a Virtual Environment:**
    *   **macOS / Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   **Windows:**
        ```powershell
        python -m venv venv
        .\venv\Scripts\Activate.ps1
        ```

3.  **Install Required Dependencies:**
    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    Duplicate the provided template `.env.example` to create a working config:
    ```bash
    cp .env.example .env
    ```
    *Open the `.env` file and insert your respective credentials (see [Configuration](#-configuration)).*

5.  **Initialize the Database:**
    Open a Python terminal and run:
    ```python
    from src.app import app
    from src.db import db
    with app.app_context():
        db.create_all()
    ```

6.  **Launch the Application:**
    ```bash
    python run.py
    ```
    *Navigate to `http://127.0.0.1:5000` in your web browser.*

---

## 🐳 Docker Deployment

The application features a fully optimized Docker environment suitable for fast deployments.

1.  **Build the Container:**
    ```bash
    docker build -t voice-email-assistant .
    ```

2.  **Run the Container:**
    ```bash
    docker run -p 5000:5000 --env-file .env voice-email-assistant
    ```
    *Access the application at `http://localhost:5000`.*

---

## ⚙️ Configuration (.env Reference)

| Key | Description | Default Value |
| :--- | :--- | :--- |
| `FLASK_SECRET_KEY` | Secure session hashing key | `replace-with-a-secure-secret` |
| `DATABASE_URL` | SQLite / PostgreSQL connection URI | `sqlite:///data.db` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID credentials | *(Get from Google Console)* |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Secret key credentials | *(Get from Google Console)* |
| `GOOGLE_LOGIN_REDIRECT_URI` | Auth redirect callback path | `http://127.0.0.1:5000/auth/callback` |
| `GOOGLE_GMAIL_REDIRECT_URI`| Gmail sync redirect callback path | `http://127.0.0.1:5000/auth/gmail/callback` |
| `HF_TOKEN` | HuggingFace Access Token | *(Required for HF pipeline downloads)* |
| `WHISPER_MODEL_SIZE` | OpenAI Whisper local model download size | `tiny.en` |
| `HF_WHISPER_MODEL` | HuggingFace Whisper model path | `openai/whisper-small` |
| `HF_MODEL_NAME` | Instruction drafting LLM | `Qwen/Qwen2.5-1.5B-Instruct` |
| `TRANSLATION_HF_MODEL` | HuggingFaceTranslation model path | `facebook/mbart-large-50-many-to-many-mmt`|

---

## 🧪 Verification & Testing

Our codebase contains comprehensive unit and integration tests.

### Running Test Suite
Execute the testing suite with:
```bash
pytest
```

### Viewing Code Coverage
Run pytest with coverage report to evaluate covered lines:
```bash
pytest --cov=src --cov-report=term-missing
```

---

## 🤝 Contribution Guidelines

We welcome contributions to the **Voice-Based Email & Messaging Assistant**!
1.  **Branching Strategy:** Cut features from `dev` using `feature/your-feature-name` naming schemas.
2.  **Code Styling:** Run Prettier on HTML/CSS/JS configurations and keep Python files PEP8 compliant.
3.  **Pull Requests:** Target `dev` for initial merges. Ensure your pipeline builds green and is supported by corresponding unit tests.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE) — see the root license file for usage specifications.
