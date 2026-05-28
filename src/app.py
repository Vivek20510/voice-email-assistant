import os

from dotenv import load_dotenv

from flask import Flask, redirect, session, url_for


from src.db import init_db

from src.web.auth_routes import auth_bp, channel_bp

from src.web.ai_panel_routes import ai_panel_bp

from src.web.compose_routes import compose_bp

from src.web.email_routes import email_bp, messages_bp

from src.web.nlp_routes import nlp_bp

from src.web.summary_routes import summary_bp

from src.web.translation_routes import translation_bp  # ✅ added

# ✅ Load environment variables

load_dotenv()


def create_app(test_config=None):
    """Create and configure the Flask application."""

    root_dir = os.path.dirname(os.path.dirname(__file__))

    app = Flask(
        __name__,
        static_folder=os.path.join(root_dir, "static"),
        static_url_path="/static",
        template_folder=os.path.join(root_dir, "templates"),
    )

    # ✅ Configurations

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

    database_url = os.getenv("DATABASE_URL")

    if database_url:

        app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    else:

        db_path = os.path.join(root_dir, "data.db")

        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ✅ Apply test config if exists

    if test_config is not None:

        app.config.update(test_config)

    # ✅ Initialize database

    init_db(app)

    # ✅ Register blueprints

    app.register_blueprint(auth_bp)

    app.register_blueprint(channel_bp)

    app.register_blueprint(email_bp)

    app.register_blueprint(messages_bp)

    app.register_blueprint(ai_panel_bp)

    app.register_blueprint(compose_bp)

    app.register_blueprint(nlp_bp)

    app.register_blueprint(summary_bp)

    app.register_blueprint(translation_bp)  # ✅ newly added

    # ✅ Routes

    @app.route("/")
    def index():

        if session.get("user_id"):

            return redirect(url_for("auth.dashboard"))

        return redirect(url_for("auth.login_form"))

    @app.route("/health")
    def health():

        return {"status": "ok"}

    return app


# ✅ Create app instance

app = create_app()


# ✅ Run directly

if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5000, debug=True)
