"""Entrypoint de Vercel: el runtime de Python detecta la app WSGI `app`."""

import sys
from pathlib import Path

# El bundle de Vercel ejecuta desde /var/task; aseguramos que el paquete
# `app/` de la raiz del repo sea importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402

app = create_app()
