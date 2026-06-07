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

    if "users" in tables:

        user_columns = {column["name"] for column in inspector.get_columns("users")}

        user_column_definitions = {
            "security_question_1": "VARCHAR(255)",
            "security_answer_1_hash": "VARCHAR(255)",
            "security_question_2": "VARCHAR(255)",
            "security_answer_2_hash": "VARCHAR(255)",
            "security_failed_attempts": "INTEGER NOT NULL DEFAULT 0",
            "security_locked_until": "DATETIME",
        }

        with db.engine.begin() as connection:

            for column_name, column_type in user_column_definitions.items():

                if column_name not in user_columns:

                    connection.execute(
                        text(
                            f"ALTER TABLE users ADD COLUMN "
                            f"{column_name} {column_type}"
                        )
                    )

    if "user_preferences" not in tables:

        with db.engine.begin() as connection:

            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        id INTEGER NOT NULL PRIMARY KEY,
                        user_id INTEGER NOT NULL UNIQUE,
                        ai_data_usage_enabled BOOLEAN NOT NULL DEFAULT 1,
                        preferred_language VARCHAR(64) NOT NULL DEFAULT 'English',
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES users (id)
                    )
                    """
                )
            )

    inspector = inspect(db.engine)
    preference_columns = {
        column["name"]
        for column in inspector.get_columns("user_preferences")
    }

    if "preferred_language" not in preference_columns:

        with db.engine.begin() as connection:

            connection.execute(
                text(
                    "ALTER TABLE user_preferences "
                    "ADD COLUMN preferred_language VARCHAR(64) "
                    "NOT NULL DEFAULT 'English'"
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
