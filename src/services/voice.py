"""Voice transcription service stubs for Sprint 1."""

from __future__ import annotations
from typing import Any


def transcribe_audio(file_path: str, language: str | None = None) -> dict[str, Any]:
    """Transcribe audio from a file path using Whisper.

    The implementation uses openai-whisper in production, but falls back to a
    placeholder response if the package is unavailable in the current environment.
    """
    try:
        import whisper

        model = whisper.load_model('tiny')
        transcription = model.transcribe(file_path, language=language) if language else model.transcribe(file_path)
        return {
            'text': transcription.get('text', ''),
            'language': transcription.get('language', language or 'en'),
            'segments': transcription.get('segments', []),
        }
    except ImportError:
        return {
            'text': 'Transcription placeholder: whisper package not installed.',
            'language': language or 'en',
            'segments': [],
        }
