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
    tables = inspector.get_table_names()

    if "user_preferences" not in tables:

        with db.engine.begin() as connection:

            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        id INTEGER NOT NULL PRIMARY KEY,
                        user_id INTEGER NOT NULL UNIQUE,
                        ai_data_usage_enabled BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES users (id)
                    )
                    """
                )
            )

    if "user_tokens" not in tables:

        return

    columns = {column["name"] for column in inspector.get_columns("user_tokens")}

    if "account_email" not in columns:

        with db.engine.begin() as connection:

            connection.execute(
                text("ALTER TABLE user_tokens ADD COLUMN account_email VARCHAR(255)")
            )
