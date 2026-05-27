"""Database initialization and configuration."""

from sqlalchemy import inspect, text


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

        _ensure_schema_compatibility()


def _ensure_schema_compatibility():
    """Apply lightweight schema fixes for existing SQLite databases."""

    inspector = inspect(db.engine)

    if "user_tokens" not in inspector.get_table_names():

        return

    columns = {column["name"] for column in inspector.get_columns("user_tokens")}

    if "account_email" not in columns:

        with db.engine.begin() as connection:

            connection.execute(
                text("ALTER TABLE user_tokens ADD COLUMN account_email VARCHAR(255)")
            )
