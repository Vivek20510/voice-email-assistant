import subprocess
import sys
from types import SimpleNamespace

from src.services import qwen_reply_service


def _reset_reply_service(monkeypatch):
    monkeypatch.setattr(qwen_reply_service, "_local_attempted", False)
    monkeypatch.setattr(qwen_reply_service, "_hf_attempted", False)
    monkeypatch.setattr(qwen_reply_service, "_model", None)
    monkeypatch.setattr(qwen_reply_service, "_tokenizer", None)
    monkeypatch.setattr(qwen_reply_service, "_hf_client", None)
    monkeypatch.setattr(qwen_reply_service, "REPLY_MODEL_MODE", "fallback")


def test_qwen_reply_service_imports_without_local_model_path():
    script = (
        "import os; "
        "os.environ.pop('QWEN_REPLY_LOCAL_PATH', None); "
        "os.environ.pop('QWEN_LOCAL_PATH', None); "
        "import src.services.qwen_reply_service as service; "
        "print(service.get_reply_model_mode())"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "fallback"


def test_generate_qwen_replies_uses_local_generation(monkeypatch):
    _reset_reply_service(monkeypatch)
    monkeypatch.setattr(qwen_reply_service, "load_local_model", lambda: True)
    monkeypatch.setattr(qwen_reply_service, "load_hf_api", lambda: False)
    monkeypatch.setattr(
        qwen_reply_service,
        "generate_local_reply",
        lambda text, tone: f"Hello, I will review the {tone} project update and reply shortly.",
    )

    replies = qwen_reply_service.generate_qwen_replies("Project update")

    assert set(replies) == {"casual", "formal", "professional"}
    assert qwen_reply_service.get_reply_model_mode() == "local"


def test_generate_qwen_replies_uses_hosted_generation(monkeypatch):
    _reset_reply_service(monkeypatch)
    monkeypatch.setattr(qwen_reply_service, "load_local_model", lambda: False)
    monkeypatch.setattr(qwen_reply_service, "load_hf_api", lambda: True)
    monkeypatch.setattr(
        qwen_reply_service,
        "generate_hf_reply",
        lambda text, tone: f"Hello, I will review the {tone} project update and reply shortly.",
    )

    replies = qwen_reply_service.generate_qwen_replies("Project update")

    assert set(replies) == {"casual", "formal", "professional"}
    assert qwen_reply_service.get_reply_model_mode() == "hf_api"


def test_generate_qwen_replies_replaces_unavailable_provider_text(monkeypatch):
    _reset_reply_service(monkeypatch)
    monkeypatch.setattr(qwen_reply_service, "load_local_model", lambda: False)
    monkeypatch.setattr(qwen_reply_service, "load_hf_api", lambda: True)
    monkeypatch.setattr(
        qwen_reply_service,
        "generate_hf_reply",
        lambda text, tone: (
            "AI service is currently unavailable. Basic assistant mode is active. "
            "Your query: reply to this email."
        ),
    )

    replies = qwen_reply_service.generate_qwen_replies(
        "Please review the quarterly report by Friday."
    )

    assert qwen_reply_service.get_reply_model_mode() == "fallback"
    assert all("quarterly report" in reply for reply in replies.values())
    assert all("AI service is currently unavailable" not in reply for reply in replies.values())


def test_generate_qwen_replies_uses_contextual_fallback_without_provider(monkeypatch):
    _reset_reply_service(monkeypatch)
    monkeypatch.setattr(qwen_reply_service, "load_local_model", lambda: False)
    monkeypatch.setattr(qwen_reply_service, "load_hf_api", lambda: False)

    replies = qwen_reply_service.generate_qwen_replies(
        "Please review the quarterly report by Friday."
    )

    assert qwen_reply_service.get_reply_model_mode() == "fallback"
    assert set(replies) == {"casual", "formal", "professional"}
    assert all("quarterly report" in reply for reply in replies.values())


def test_generate_hf_reply_extracts_chat_completion_content(monkeypatch):
    client = SimpleNamespace(
        chat_completion=lambda **kwargs: SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello,\n\nI will review the report and follow up shortly.\n\nBest"
                    )
                )
            ]
        )
    )
    monkeypatch.setattr(qwen_reply_service, "_hf_client", client)

    reply = qwen_reply_service.generate_hf_reply("Review the report.", "professional")

    assert reply.startswith("Hello,")
