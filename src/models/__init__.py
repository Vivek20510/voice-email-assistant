"""Database models for the voice-email-assistant application."""

from datetime import datetime, timezone

from src.db import db


class User(db.Model):
    """User model for storing account and authentication details."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # Security questions and hashed answers (optional in DB; enforced at signup)
    security_question_1 = db.Column(db.String(255), nullable=True)
    security_answer_1_hash = db.Column(db.String(255), nullable=True)
    security_question_2 = db.Column(db.String(255), nullable=True)
    security_answer_2_hash = db.Column(db.String(255), nullable=True)
    # Brute-force protection for security question verification
    security_failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    security_locked_until = db.Column(db.DateTime, nullable=True)

    tokens = db.relationship(
        "UserToken", back_populates="user", cascade="all, delete-orphan"
    )
    email_messages = db.relationship(
        "EmailMessage", back_populates="user", cascade="all, delete-orphan"
    )
    conversations = db.relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    preferences = db.relationship(
        "UserPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


class UserToken(db.Model):
    """User token storage for connected services."""

    __tablename__ = "user_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    service = db.Column(db.String(128), nullable=False)
    account_email = db.Column(db.String(255), nullable=True)
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="tokens")

    def __repr__(self):
        return f"<UserToken id={self.id} service={self.service} user_id={self.user_id}>"


class UserPreference(db.Model):
    """Per-user application preferences."""

    __tablename__ = "user_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )
    ai_data_usage_enabled = db.Column(db.Boolean, nullable=False, default=True)
    preferred_language = db.Column(db.String(64), nullable=False, default="English")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="preferences")

    def __repr__(self):
        return (
            f"<UserPreference user_id={self.user_id} "
            f"ai_data_usage_enabled={self.ai_data_usage_enabled} "
            f"preferred_language={self.preferred_language}>"
        )


class Conversation(db.Model):
    """Conversation model for messaging and chat tracking."""

    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    telegram_chat_id = db.Column(db.String(255), unique=True, nullable=True)
    state = db.Column(db.String(128), nullable=True)
    context = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="conversations")
    messages = db.relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Conversation id={self.id} telegram_chat_id={self.telegram_chat_id}>"


class Message(db.Model):
    """Message model for conversation history."""

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversations.id"), nullable=False
    )
    sender = db.Column(db.String(64), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = db.relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return (
            f"<Message id={self.id} sender={self.sender} "
            f"conversation_id={self.conversation_id}>"
        )


class EmailMessage(db.Model):
    """Placeholder model for stored email messages."""

    __tablename__ = "email_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    gmail_id = db.Column(db.String(255), nullable=True)
    subject = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=True)
    to = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="email_messages")

    def __repr__(self):
        return f"<EmailMessage id={self.id} user_id={self.user_id}>"


class ReadMessage(db.Model):
    """Local read-state marker for provider messages."""

    __tablename__ = "read_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    channel = db.Column(db.String(64), nullable=False)
    message_id = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "channel",
            "message_id",
            name="uq_read_messages_user_channel_message",
        ),
    )

    def __repr__(self):
        return (
            f"<ReadMessage user_id={self.user_id} "
            f"channel={self.channel} message_id={self.message_id}>"
        )
