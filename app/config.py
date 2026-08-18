import os
from dataclasses import dataclass, field


class ConfigError(RuntimeError):
    """Falta configuracion obligatoria para arrancar el servicio."""


DEFAULT_ALLOWED_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    }
)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} debe ser un entero, se recibio {raw!r}") from exc


@dataclass(frozen=True)
class Config:
    """Configuracion del servicio.

    Se construye con `from_env()` *despues* de cargar el .env, no al importar
    el modulo: de lo contrario el orden de imports decide si hay o no valores.
    """

    GEMINI_API_KEY: str
    API_TOKEN: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    # Vercel corta el body antes de que llegue aqui, pero este limite protege
    # el dev local y produce un 413 en JSON en vez de reventar.
    MAX_CONTENT_LENGTH: int = 10 * 1024 * 1024
    ALLOWED_MIME_TYPES: frozenset[str] = field(default=DEFAULT_ALLOWED_MIME_TYPES)

    @classmethod
    def from_env(cls) -> "Config":
        # Acepta los dos nombres para no romper el .env que ya tenias.
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_APIKEY") or ""
        if not api_key:
            raise ConfigError("Falta GEMINI_API_KEY en el entorno.")

        token = os.environ.get("API_TOKEN", "").strip()
        if not token:
            raise ConfigError(
                "Falta API_TOKEN. Genera uno con `openssl rand -hex 32`; sin el, "
                "cualquiera puede gastar tu cuota de Gemini."
            )

        return cls(
            GEMINI_API_KEY=api_key,
            API_TOKEN=token,
            GEMINI_MODEL=os.environ.get("GEMINI_MODEL", cls.GEMINI_MODEL),
            MAX_CONTENT_LENGTH=_int_env("MAX_UPLOAD_BYTES", cls.MAX_CONTENT_LENGTH),
        )
