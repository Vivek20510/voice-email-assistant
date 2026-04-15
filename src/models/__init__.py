"""Database models for the voice-email-assistant application."""
from datetime import datetime
from src.db import db


class User(db.Model):
    """User model for storing account and authentication details."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tokens = db.relationship('UserToken', back_populates='user', cascade='all, delete-orphan')
    email_messages = db.relationship('EmailMessage', back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


class UserToken(db.Model):
    """User token storage for connected services."""
    __tablename__ = 'user_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service = db.Column(db.String(128), nullable=False)
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='tokens')

    def __repr__(self):
        return f"<UserToken id={self.id} service={self.service} user_id={self.user_id}>"


class EmailMessage(db.Model):
    """Placeholder model for stored email messages."""
    __tablename__ = 'email_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    gmail_id = db.Column(db.String(255), nullable=True)
    subject = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=True)
    to = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='email_messages')

    def __repr__(self):
        return f"<EmailMessage id={self.id} user_id={self.user_id}>"
