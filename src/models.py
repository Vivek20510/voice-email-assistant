"""Database models for the voice-email-assistant application."""
from datetime import datetime
from src.db import db


class User(db.Model):
    """User model for storing user account information.
    
    Day 1: Stub with minimal fields
    Day 2: Will add email and password_hash fields
    """
    __tablename__ = 'user'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # TODO: Add email field (Day 2 by Urmila)
    # email = db.Column(db.String(255), unique=True, nullable=False)
    
    # TODO: Add password_hash field (Day 2 by Urmila)
    # password_hash = db.Column(db.String(255), nullable=False)
    
    def __repr__(self):
        """String representation for debugging."""
        return f"<User id={self.id}>"
