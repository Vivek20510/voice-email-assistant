# Setup Guide

## Local Setup

1. Create a Python virtual environment.
2. Install dependencies.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and update values.

```bash
copy .env.example .env
```

4. Run the application.

```bash
python run.py
```

5. Verify service.

Open `http://localhost:5000/health` and confirm the response returns `{"status":"ok"}`.

## Notes

- The application uses SQLite by default via `data.db`.
- Email and messaging features are currently stubbed and will be expanded in later sprints.
- The voice transcription service path is a placeholder when `whisper` is not installed.
