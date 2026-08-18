import logging
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.prompts import TRANSCRIBE_IMAGE

logger = logging.getLogger(__name__)

# Codigos que suelen resolverse solos: saturacion del modelo o rate limit.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.5


class GeminiError(RuntimeError):
    """El modelo fallo o devolvio una respuesta inutilizable.

    `status` es el codigo HTTP que debe propagarse al cliente para que el
    Atajo pueda distinguir "reintenta" (503) de "algo esta mal" (502).
    """

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class ChatbotManager:
    """Envoltura fina sobre google-genai.

    Se instancia una sola vez por proceso: en Vercel la instancia sobrevive
    entre invocaciones calientes, asi que reutilizar el cliente ahorra el
    handshake TLS en cada request.
    """

    api_key: str
    model: str = "gemini-3.6-flash"
    client: genai.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # Ojo: como atributo de clase con default esto se evaluaba al importar
        # el modulo (y `api_key` ni siquiera existia en ese scope).
        self.client = genai.Client(api_key=self.api_key)

    def scan_image(self, image_bytes: bytes, mime_type: str) -> str:
        response = self._generate(
            contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
            config=types.GenerateContentConfig(
                system_instruction=TRANSCRIBE_IMAGE,
                temperature=0,
            ),
        )

        text = (response.text or "").strip()
        if not text:
            # Pasa cuando el prompt o la imagen se bloquean por safety filters.
            reason = getattr(response, "prompt_feedback", None)
            raise GeminiError(f"El modelo no devolvio texto (feedback={reason}).", 422)
        return text

    def _generate(self, *, contents: list, config: types.GenerateContentConfig):
        """Llama al modelo reintentando los fallos transitorios."""
        last: GeminiError | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self.client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except genai_errors.APIError as exc:
                status = getattr(exc, "code", 502) or 502
                last = GeminiError(_clean(exc), status if status in RETRYABLE_STATUS else 502)
                if status not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS:
                    raise last from exc
                delay = BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Gemini %s en intento %s/%s; reintento en %.1fs",
                    status, attempt, MAX_ATTEMPTS, delay,
                )
                time.sleep(delay)
            except Exception as exc:  # red caida, DNS, api key invalida...
                raise GeminiError(str(exc), 502) from exc

        raise last or GeminiError("Fallo desconocido al llamar al modelo.")


def _clean(exc: genai_errors.APIError) -> str:
    """Mensaje corto para el cliente, sin el volcado JSON completo."""
    message = getattr(exc, "message", None) or str(exc)
    return message.strip()
