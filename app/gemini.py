from dataclasses import dataclass, field

from google import genai
from google.genai import types

from app.prompts import TRANSCRIBE_IMAGE


class GeminiError(RuntimeError):
    """El modelo fallo o devolvio una respuesta inutilizable."""


@dataclass
class ChatbotManager:
    """Envoltura fina sobre google-genai.

    Se instancia una sola vez por proceso: en Vercel la instancia sobrevive
    entre invocaciones calientes, asi que reutilizar el cliente ahorra el
    handshake TLS en cada request.
    """

    api_key: str
    model: str = "gemini-2.5-flash"
    client: genai.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # Ojo: como atributo de clase con default esto se evaluaba al importar
        # el modulo (y `api_key` ni siquiera existia en ese scope).
        self.client = genai.Client(api_key=self.api_key)

    def scan_image(self, image_bytes: bytes, mime_type: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
                config=types.GenerateContentConfig(
                    system_instruction=TRANSCRIBE_IMAGE,
                    temperature=0,
                ),
            )
        except Exception as exc:  # errores de red, cuota, api key invalida...
            raise GeminiError(str(exc)) from exc

        text = (response.text or "").strip()
        if not text:
            # Pasa cuando el prompt o la imagen se bloquean por safety filters.
            reason = getattr(response, "prompt_feedback", None)
            raise GeminiError(f"El modelo no devolvio texto. feedback={reason}")
        return text
