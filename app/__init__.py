import logging

from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.gemini import ChatbotManager
from app.routes import ApiError, bp


def create_app(config: Config | None = None) -> Flask:
    load_dotenv()
    config = config or Config.from_env()

    app = Flask(__name__)
    app.config.from_object(config)
    app.logger.setLevel(logging.INFO)

    # Un solo cliente por proceso, reutilizado entre invocaciones calientes.
    app.extensions["chatbot"] = ChatbotManager(
        api_key=config.GEMINI_API_KEY,
        model=config.GEMINI_MODEL,
    )

    app.register_blueprint(bp)
    _register_error_handlers(app)
    return app


def _register_error_handlers(app: Flask) -> None:
    """El Atajo solo sabe leer JSON: nunca devolvemos las paginas HTML de Flask."""

    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        return jsonify({"ok": False, "error": exc.message}), exc.status

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        return jsonify({"ok": False, "error": exc.description}), exc.code

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception):
        app.logger.exception("Error no controlado")
        return jsonify({"ok": False, "error": "Error interno del servidor."}), 500
