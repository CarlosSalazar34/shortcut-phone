"""Entrypoint de la aplicacion.

Vercel usa este mismo archivo como entrypoint (preset `flask`): detecta la
app WSGI `app` de nivel superior. El bloque `__main__` solo corre en local.
"""

import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
