from flask import Flask
from src.db import db, init_db
from src import models  # noqa: F401 - import models so they're registered with SQLAlchemy


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configure SQLite database (absolute path to project root)
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database
    init_db(app)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()