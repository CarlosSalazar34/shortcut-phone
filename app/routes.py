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


def _sniff_mime(data: bytes) -> str | None:
    """Deduce el tipo por los magic bytes.

    Atajos no siempre etiqueta bien la foto; los bytes nunca mienten.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
        return "image/heic"
    return None


def _debug_summary() -> str:
    """Que llego realmente, para poder depurar desde el telefono."""
    return (
        f"content_type={request.content_type or 'ninguno'} "
        f"archivos={list(request.files.keys()) or 'ninguno'} "
        f"campos={list(request.form.keys()) or 'ninguno'} "
        f"bytes_cuerpo={request.content_length or 0}"
    )


def _image_from_request() -> tuple[bytes, str]:
    """Acepta las tres formas en que un Atajo puede mandar una imagen.

    1. multipart/form-data  -> 'Solicitar cuerpo: Formulario' con un campo Archivo
    2. cuerpo binario crudo -> 'Solicitar cuerpo: Archivo'
    3. JSON con base64      -> 'Solicitar cuerpo: JSON' + accion Codificar en base64

    En multipart aceptamos cualquier nombre de campo: Atajos no siempre respeta
    el que escribes, y exigir `file` solo genera un 400 dificil de diagnosticar.
    """
    data: bytes
    mime_type: str

    if request.files:
        storage = request.files.get("file") or next(iter(request.files.values()))
        data = storage.read()
        mime_type = storage.mimetype or ""
    elif request.is_json:
        payload = request.get_json(silent=True) or {}
        raw = payload.get("image_base64")
        if not raw:
            raise ApiError("Falta `image_base64` en el cuerpo JSON.")
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ApiError("`image_base64` no es base64 valido.") from exc
        mime_type = payload.get("mime_type", "")
    else:
        # Cuerpo crudo: 'Solicitar cuerpo: Archivo' en Atajos.
        data = request.get_data()
        mime_type = request.mimetype or ""

    if not data:
        raise ApiError(
            "No llego ninguna imagen. ❌ En el Atajo, pon `Solicitar cuerpo: Archivo` "
            f"y como valor la foto. Recibido: {_debug_summary()}"
        )

    # Los magic bytes mandan sobre la etiqueta declarada.
    mime_type = (_sniff_mime(data) or mime_type).split(";")[0].strip().lower()

    allowed = current_app.config["ALLOWED_MIME_TYPES"]
    if mime_type not in allowed:
        raise ApiError(
            f"Tipo `{mime_type or 'desconocido'}` no soportado. "
            f"Permitidos: {', '.join(sorted(allowed))}.",
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
