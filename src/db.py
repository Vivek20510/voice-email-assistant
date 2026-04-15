"""Database initialization and configuration."""
from flask_sqlalchemy import SQLAlchemy

# Create SQLAlchemy instance (no app binding yet)
db = SQLAlchemy()


def init_db(app):
    """Initialize the database with the Flask app.
    
    Args:
        app: Flask application instance
    
    This function:
    - Binds SQLAlchemy to the Flask app
    - Creates all tables in the database
    """
    db.init_app(app)
    
    # Create all tables within app context
    with app.app_context():
        db.create_all()
