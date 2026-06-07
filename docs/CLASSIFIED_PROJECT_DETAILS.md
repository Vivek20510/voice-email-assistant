# 🔒 Classified Project Reference Manual

### _Internal Development Team Only — Confidential Technical Documentation_

---

## ⚠️ Security & Classification Notice

This document contains proprietary architectural details, model pipelines, API structures, local desktop automation bindings, and system credentials formats for the **Voice-Based Email & Messaging Assistant**. This manual is restricted to verified project developers and system maintainers.

---

## 🗺️ System Architecture Overview

The application follows a modular Model-View-Controller (MVC) system built with **Flask**, backed by an asynchronous local AI pipeline, and client-side Single Page Application (SPA) routing.

```mermaid
graph TD
    A[SPA UI - Vanilla HTML5/CSS3/JS] -->|AJAX / REST API| B[Flask Application Routing]
    B -->|User Auth & Profiles| C[Auth Service]
    B -->|AI Context & Queries| D[AI & NLP Services]
    B -->|Email Synced Data| E[Email Service - Gmail OAuth / Outlook COM]

    C -->|ORM Sessions| F[(SQLite Database)]
    E -->|MAPI Dispatch| G[Local Desktop Microsoft Outlook]
    E -->|Google OAuth v2| H[Google API Gateway]

    D -->|Local Inference| I[Local PyTorch Models - Whisper / Qwen]
    D -->|Failover Pipeline| J[Hugging Face Inference Hub]

    F -->|Migration Pipeline| K[(MySQL Enterprise Database)]
```

---

## 🗄️ Database Entity-Relationship Specification

The internal data store is managed via **Flask-SQLAlchemy**. The tables enforce rigorous relationship hierarchies and cascading rules to maintain database integrity.

### 1. `users` Table

Stores primary accounts and system identity bindings.

- `id` (Integer, Primary Key): Auto-incremented primary user ID.
- `email` (String(255), Unique, Not Null): Verified login email.
- `password_hash` (String(255), Not Null): Hashed credentials (using **Bcrypt**).
- `created_at` (DateTime, Default UTC): Timestamp of account creation.

#### Relationships:

- `tokens` $\rightarrow$ `UserToken` (One-to-Many, cascade="all, delete-orphan")
- `email_messages` $\rightarrow$ `EmailMessage` (One-to-Many, cascade="all, delete-orphan")
- `conversations` $\rightarrow$ `Conversation` (One-to-Many, cascade="all, delete-orphan")
- `preferences` $\rightarrow$ `UserPreference` (One-to-One, cascade="all, delete-orphan")

### 2. `user_tokens` Table

Maintains OAuth credentials and system connection states for active providers.

- `id` (Integer, Primary Key)
- `user_id` (Integer, Foreign Key `users.id`, Not Null)
- `service` (String(128), Not Null): Identifies the channel provider (`gmail` or `outlook`).
- `account_email` (String(255), Nullable): The sync target email.
- `access_token` (Text, Nullable): Valid API access token.
- `refresh_token` (Text, Nullable): Long-lived offline refresh token.
- `expires_at` (DateTime, Nullable): Token expiration window in UTC.
- `created_at` (DateTime, Default UTC)

### 3. `user_preferences` Table

Customizes layout density, translation targets, and AI features.

- `id` (Integer, Primary Key)
- `user_id` (Integer, Foreign Key `users.id`, Unique, Not Null)
- `ai_data_usage_enabled` (Boolean, Default True): Controls opt-in for AI features.
- `preferred_language` (String(64), Default "English"): Source target for translations.
- `created_at` / `updated_at` (DateTime, Default UTC)

### 4. `conversations` & `messages` Tables

Enforces history models specifically for connected external chats (e.g. Telegram).

- **`conversations` Table:**
  - `id` (Integer, Primary Key)
  - `user_id` (Integer, Foreign Key `users.id`, Not Null)
  - `telegram_chat_id` (String(255), Unique, Nullable): Unique reference to active Telegram user.
  - `state` / `context` (String / Text, Nullable): Stores conversational steps or active state data.
- **`messages` Table:**
  - `id` (Integer, Primary Key)
  - `conversation_id` (Integer, Foreign Key `conversations.id`, Not Null)
  - `sender` (String(64), Not Null): Identifies sender (`user` or `assistant`).
  - `text` (Text, Not Null): Text message payload.
  - `created_at` (DateTime, Default UTC)

### 5. `read_messages` Table

Tracks read states for dynamic inbox markers.

- `id` (Integer, Primary Key)
- `user_id` (Integer, Foreign Key `users.id`, Not Null)
- `channel` (String(64), Not Null): Provider label (`gmail` or `outlook`).
- `message_id` (String(255), Not Null): Provider-specific email ID.
- `created_at` (DateTime, Default UTC)
- _Constraint:_ `uq_read_messages_user_channel_message` (UniqueConstraint on user_id, channel, message_id).

---

## 🔄 Database Migration Roadmap: SQLite to MySQL

For production scale-out, migrating from localized SQLite files to **MySQL** is essential. Developers must adhere to the following sequence to execute this migration successfully.

### Step 1: Mapping Schema & Dialect Differences

SQLite dynamic schemas do not enforce length limits or strong types as strictly as MySQL does. Review the SQL type adaptations:

- **Booleans:** SQLite stores booleans as `0` or `1` (Integers). MySQL maps them to `TINYINT(1)` or `BOOLEAN`. Ensure Flask-SQLAlchemy maps column structures to standard dialects.
- **Foreign Key Constraints:** Enforce correct constraint names. MySQL strictly validates parent record availability. SQLite requires manually setting `PRAGMA foreign_keys = ON;`.
- **String Lengths:** SQLite handles unlimited lengths for strings by default. Ensure all `db.String(N)` columns in the ORM specify a distinct length (e.g. `db.String(255)`) to prevent MySQL compilation errors.

### Step 2: Install Migration Tools

The recommended approach utilizes the python-based CLI migration wrapper `sqlite3-to-mysql`, which handles type translation and schema compilation smoothly.

```bash
pip install sqlite3-to-mysql pymysql
```

### Step 3: Run the Migration CLI

With the target MySQL server created and database allocated, execute:

```bash
sqlite3-to-mysql \
  -f ./instance/data.db \
  -u mysql_developer \
  -p \
  -h localhost \
  -P 3306 \
  -d voice_assistant_db \
  -e \
  --mysql-engine=InnoDB
```

- `-f`: Source SQLite database file.
- `-d`: Name of the target MySQL database.
- `-e`: Exclude structural layout dumps (only export clean tables).
- `--mysql-engine=InnoDB`: Recommends MySQL’s Transactional Engine to preserve primary integrity and foreign keys.

### Step 4: Configure App Connection

Update the development `.env` connection variables:

```ini
# From SQLite:
# DATABASE_URL=sqlite:///data.db

# To MySQL:
DATABASE_URL=mysql+pymysql://mysql_developer:secure_password@localhost:3306/voice_assistant_db
```

---

## 🎙️ Local Outlook Desktop COM Automation (Windows)

When running on Windows platforms, the assistant connects directly to classic desktop Microsoft Outlook via local **pywin32 MAPI COM objects**, bypassing network limitations.

### COM Lifecycle Management

- **Initialization:** Every separate execution thread using COM must register inside the Windows Thread Pool using COM App Dispatch:
  ```python
  import pythoncom
  import win32com.client
  pythoncom.CoInitialize()
  app = win32com.client.Dispatch("Outlook.Application")
  ```
- **Session Logon:** Instantiates a clean MAPI namespace session:
  ```python
  namespace = app.GetNamespace("MAPI")
  namespace.Logon("", "", False, False)
  ```
- **Inbox Reading & Sorting:** Pulls items from folder index `6` (Default Inbox Folder index in classic Outlook), sorts by received timestamp descending, and filters specifically for standard Mail items (`Class == 43`).
- **Vulnerability Warning:** Developers must release the thread binding at the termination of COM sequences (`pythoncom.CoUninitialize()`) inside a `finally` block to prevent resource exhaustion or COM memory lockouts.

---

## 🤖 Deep-Dive AI Lifecycle & Failover Engines

The AI services implement a strict, three-layered fallback chain to guarantee high availability even under local CPU resource starvation.

```text
               ┌────────────────────────┐
               │    Local Pipeline      │
               │ (PyTorch GPU / CPU)    │
               └───────────┬────────────┘
                           │ (Local path configured?)
                           ├───────────────────────────────┐
                           ▼ [YES]                         ▼ [NO]
               ┌────────────────────────┐      ┌────────────────────────┐
               │ Try Local Model Load   │      │   Skip Local Pipeline  │
               └───────────┬────────────┘      └───────────┬────────────┘
                           │                               │
             ┌─────────────┴─────────────┐                 │
             ▼ [Success]                 ▼ [Failed]        │
┌────────────────────────┐    ┌────────────────────────┐   │
│ Execute Local Inference│    │ Try HuggingFace API    │◄──┘
└────────────────────────┘    └───────────┬────────────┘
                                          │
                            ┌─────────────┴─────────────┐
                            ▼ [Success]                 ▼ [Failed]
              ┌────────────────────────┐    ┌────────────────────────┐
              │ Execute HF Inference   │    │  Static Template Mode  │
              └────────────────────────┘    │  (Fallback responses)  │
                                            └────────────────────────┘
```

### 1. Unified Speech-to-Text Pipeline (`voice.py`)

1.  **Format Transcoding:** Browser blobs (often `.webm` encoding) are converted to raw 16kHz mono WAV format via local `ffmpeg` (wrapped by `imageio_ffmpeg` executable helpers).
2.  **Inference:**
    - **Layer 1 (Local):** `openai-whisper` loads the specified size model (e.g. `tiny.en` loaded deterministically with `temperature=0.0`).
    - **Layer 2 (Remote):** Fallback API dispatch calls the HuggingFace ASR inference endpoint via `InferenceClient`.
3.  **Noise Phrase Filtering:** To combat Whisper's susceptibility to ambient sound/silence hallucinations, transcripts are automatically evaluated against `_NOISE_PHRASES` (e.g., matching common hallucinations like `"i used to do the mail"`, `"thanks for watching"`). The average segment probability (`no_speech_prob`) is validated against a strict `NO_SPEECH_THRESHOLD = 0.6`.

### 2. Intelligent Draft & Reply Engine (`qwen_draft_service.py`)

Generates rich template emails based on input instructions.

- **Engine Target:** `Qwen/Qwen2.5-1.5B-Instruct`
- **Prompt Injector:** Formats custom instructions containing rules for tone mappings (`casual`, `formal`, `professional`) and constraints (e.g. strict text output, no markdown tags, and no default headers).

### 3. Translation & NLP Context Engines

- **Translation (`translation.py`):** Utilizes local or hosted `mbart-large-50-many-to-many-mmt` pipelines, parsing input ISO language structures to handle translations in real time.
- **AI Panel Context Helper (`ai_panel_routes.py`):** Automatically compiles the context of up to **25 loaded emails**, mapping senders, dates, text snippets, and status flags into a singular textual prompt to provide accurate, in-context search summaries.

---

## 🧭 API Blueprint Routing & State Controller

The client UI operates as a fast, high-performance Single Page Application (SPA), routing views through modular API blueprint endpoints.

| Blueprint     | Prefix Path     | Responsible Controller | Core Functionality                                                                              |
| :------------ | :-------------- | :--------------------- | :---------------------------------------------------------------------------------------------- |
| `auth_bp`     | `/auth`         | `auth_routes.py`       | Handles registrations, logins, and Google OAuth callback redirect validation loops.             |
| `email_bp`    | `/api/emails`   | `email_routes.py`      | Message navigation, pagination, thread details, folder listings, and label marks.               |
| `voice_bp`    | `/api/voice`    | `voice_routes.py`      | Validates multipart audio uploads (max 10MB limit) and triggers the Whisper pipeline.           |
| `ai_panel_bp` | `/api/ai-panel` | `ai_panel_routes.py`   | The main brain route `/query` which reads natural query intents and returns structured actions. |

### SPA Client State Management (`app.js`)

- **Router:** Monitors navigation states and swaps virtual HTML containers (dashboard, message reader, composer, profiles settings) without reloading the page.
- **Authentication:** Access tokens are verified on initialization. Session parameters are cached within standard memory structures.
- **Custom Settings:** Appearance properties (such as dark theme preference and view spacing density) are persisted across sessions via `localStorage` checks.
