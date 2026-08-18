# shortcut-phone

Microservicio Flask que transcribe imágenes con Gemini, pensado para llamarse
desde un Atajo de iPhone. Desplegado en Vercel como función Python.

## Estructura

```
main.py           entrypoint: expone la app WSGI `app` (Vercel y local)
app/__init__.py   application factory + manejo de errores en JSON
app/config.py     configuración leída del entorno
app/routes.py     endpoints y validación de la petición
app/gemini.py     cliente de Gemini con reintentos
app/prompts.py    instrucción del sistema
```

## Endpoints

### `GET /`
Health check. Devuelve `{"ok": true, "model": "...", "time": "..."}`.

### `POST /scan/image`
Requiere cabecera `X-API-Token: <API_TOKEN>` (o `Authorization: Bearer <API_TOKEN>`).

Acepta tres formatos:

- **cuerpo binario crudo** (`Content-Type: image/*`) — el más simple desde Atajos
- **multipart/form-data** — se usa el campo `file`, o el primer archivo que llegue
- **application/json** con `{"image_base64": "...", "mime_type": "image/jpeg"}`

El tipo real se deduce de los magic bytes, así que una etiqueta incorrecta
(`application/octet-stream`) no rompe la petición.

Respuesta:

```json
{ "ok": true, "text": "...", "chars": 42, "mime_type": "image/jpeg", "bytes": 18422 }
```

En error siempre devuelve JSON: `{"ok": false, "error": "..."}` con 400 (petición
inválida), 401 (token), 413 (imagen muy grande), 415 (tipo no soportado),
422 (el modelo no devolvió texto), 429/503 (Gemini saturado) o 502.

## Desarrollo local

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y rellena GEMINI_API_KEY y API_TOKEN
python main.py
```

Prueba:

```bash
curl -s localhost:5000/
curl -s -X POST localhost:5000/scan/image \
  -H "X-API-Token: $API_TOKEN" \
  -F "file=@captura.png"
```

## Desplegar en Vercel

```bash
npm i -g vercel
vercel link
vercel env add GEMINI_API_KEY production
vercel env add API_TOKEN production
vercel --prod
```

Notas:

- El proyecto usa el **framework preset `flask`** de Vercel: construye toda la
  app como una función y le enruta todas las peticiones. No añadas `rewrites`
  ni un bloque `functions` — el rewrite reescribe el path y Flask deja de ver
  la ruta original (todo le llega como `/api/index` y responde 404). El
  `functions` de `vercel.json` solo acepta globs dentro de `api/`, que aquí no
  existe, y rompe el build.
- El entrypoint es `main.py` en la raíz, con `app` a nivel superior.
- Duración máxima por defecto: 300s, de sobra para una transcripción.
- El runtime de Python de Vercel usa **3.12**; el código es compatible.
- **El cuerpo de la petición no puede pasar de 4.5 MB.** Lo impone el edge de
  Vercel antes de invocar la función, así que la app no puede capturarlo: el
  cliente recibe `FUNCTION_PAYLOAD_TOO_LARGE` en texto plano, no JSON. Una foto
  de iPhone sin redimensionar lo supera con facilidad — redimensiona en el
  Atajo. `MAX_UPLOAD_BYTES` replica ese tope en local.
- La instancia de `ChatbotManager` se reutiliza entre invocaciones calientes.

## Configuración del Atajo (iPhone)

1. **Tomar foto** (o *Seleccionar fotos*).
2. **Redimensionar imagen** → Anchura `1600`, Altura `Automática`.
   Sin esto una foto de iPhone supera los 4.5 MB que admite Vercel y recibirás
   `FUNCTION_PAYLOAD_TOO_LARGE`. 1600px sobra para transcribir texto.
3. **Obtener contenido de URL**
   - URL: `https://shortcut-phone.vercel.app/scan/image` — una sola barra antes
     de `scan`; con `//scan/image` Vercel responde 308 y el Atajo se cuelga.
   - Método: `POST`
   - Encabezados: `X-API-Token` → tu `API_TOKEN` de producción
   - Cuerpo de la petición: **`Archivo`** → la foto del paso 1
4. **Obtener valor del diccionario** → clave `text`.
5. **Mostrar resultado** / **Copiar al portapapeles**.

`Archivo` es la opción más fiable: manda la foto como cuerpo binario, sin
nombres de campo que puedan no coincidir. El endpoint también acepta
`Formulario` (con cualquier nombre de campo) y `JSON` con `image_base64`.

Si algo falla, el error incluye lo que llegó de verdad:

```json
{"ok": false, "error": "No llego ninguna imagen. ❌ ... Recibido: content_type=... archivos=... campos=... bytes_cuerpo=0"}
```

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | sí | Clave de [Google AI Studio](https://aistudio.google.com/apikey). También se acepta `GEMINI_APIKEY`. |
| `API_TOKEN` | sí | Token compartido con el Atajo. Genéralo con `openssl rand -hex 32`. |
| `GEMINI_MODEL` | no | Por defecto `gemini-3.6-flash`. |
| `MAX_UPLOAD_BYTES` | no | Por defecto `4500000` (4.5 MB), el límite del edge de Vercel. |
