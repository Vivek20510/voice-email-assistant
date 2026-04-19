import os
from flask import Flask, redirect, url_for, session
from src.db import init_db
from src import models  # noqa: F401 - ensure models are registered
from src.web.auth_routes import auth_bp
from src.web.email_routes import email_bp, api_email_bp
from src.web.nlp_routes import nlp_bp, api_nlp_bp


def create_app(test_config=None):
    """Create and configure the Flask application."""
    root_dir = os.path.dirname(os.path.dirname(__file__))
    app = Flask(
        __name__,
        static_folder=os.path.join(root_dir, "static"),
        static_url_path="/static",
        template_folder=os.path.join(root_dir, "templates"),
    )

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        db_path = os.path.join(root_dir, "data.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if test_config is not None:
        app.config.update(test_config)

    init_db(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(api_email_bp)
    app.register_blueprint(nlp_bp)
    app.register_blueprint(api_nlp_bp)

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("auth.dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
