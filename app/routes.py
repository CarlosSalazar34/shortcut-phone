import base64
import binascii
import hmac
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.gemini import GeminiError

bp = Blueprint("api", __name__)


class ApiError(Exception):
    """Error de negocio que se traduce a una respuesta JSON limpia."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _extract_token() -> str:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):].strip()
    return request.headers.get("X-API-Token", "").strip()


def require_token(view):
    """Protege el endpoint con un token compartido con el Atajo."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = current_app.config["API_TOKEN"]
        if not expected:
            raise ApiError("El servidor no tiene API_TOKEN configurado.", 500)
        # compare_digest evita filtrar el token por tiempo de comparacion.
        if not hmac.compare_digest(_extract_token(), expected):
            raise ApiError("Token invalido o ausente. 🔒", 401)
        return view(*args, **kwargs)

    return wrapper


def _image_from_request() -> tuple[bytes, str]:
    """Acepta multipart/form-data (campo `file`) o JSON con base64.

    Atajos puede mandar cualquiera de los dos: 'Request Body: Form' con un
    archivo, o 'JSON' con la imagen pasada por la accion Base64 Encode.
    """
    if "file" in request.files:
        file = request.files["file"]
        if not file.filename:
            raise ApiError("El campo `file` viene vacio. 🤖")
        data = file.read()
        mime_type = file.mimetype or "application/octet-stream"
    elif request.is_json:
        payload = request.get_json(silent=True) or {}
        raw = payload.get("image_base64")
        if not raw:
            raise ApiError("Falta `image_base64` en el cuerpo JSON.")
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ApiError("`image_base64` no es base64 valido.") from exc
        mime_type = payload.get("mime_type", "image/jpeg")
    else:
        raise ApiError("No se subio ningun archivo. ❌")

    if not data:
        raise ApiError("La imagen esta vacia. ❌")

    mime_type = mime_type.split(";")[0].strip().lower()
    allowed = current_app.config["ALLOWED_MIME_TYPES"]
    if mime_type not in allowed:
        raise ApiError(
            f"Tipo `{mime_type}` no soportado. Permitidos: {', '.join(sorted(allowed))}.",
            415,
        )
    return data, mime_type


@bp.get("/")
def index():
    return jsonify(
        {
            "ok": True,
            "message": "api arriba. ✅",
            "model": current_app.config["GEMINI_MODEL"],
            "time": datetime.now(timezone.utc).isoformat(),
        }
    )


@bp.post("/scan/image")
@require_token
def scan_image():
    image_bytes, mime_type = _image_from_request()
    manager = current_app.extensions["chatbot"]

    try:
        text = manager.scan_image(image_bytes, mime_type)
    except GeminiError as exc:
        current_app.logger.exception("Fallo la transcripcion")
        raise ApiError(f"No se pudo procesar la imagen: {exc.message}", exc.status) from exc

    return jsonify(
        {
            "ok": True,
            "text": text,
            "chars": len(text),
            "mime_type": mime_type,
            "bytes": len(image_bytes),
        }
    )
