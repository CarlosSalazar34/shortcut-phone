# shortcut-phone

Microservicio Flask que transcribe imágenes con Gemini, pensado para llamarse
desde un Atajo de iPhone. Desplegado en Vercel como función Python.

## Estructura

```
api/index.py      entrypoint de Vercel (expone la app WSGI)
main.py           runner de desarrollo local
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

Acepta dos formatos:

- **multipart/form-data** con el campo `file`
- **application/json** con `{"image_base64": "...", "mime_type": "image/jpeg"}`

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

- El runtime de Python de Vercel usa **3.12**; el código es compatible.
- `vercel.json` reescribe todas las rutas a `api/index.py` y fija
  `maxDuration: 60s`, suficiente para una transcripción.
- El límite de cuerpo de la petición lo impone la plataforma. `MAX_UPLOAD_BYTES`
  (10 MB por defecto) solo protege el dev local y devuelve un 413 en JSON.
- La instancia de `ChatbotManager` se reutiliza entre invocaciones calientes.

## Configuración del Atajo (iPhone)

1. **Tomar foto** (o *Seleccionar fotos*).
2. **Obtener contenido de URL**
   - URL: `https://<tu-deploy>.vercel.app/scan/image`
   - Método: `POST`
   - Cabeceras: `X-API-Token` → tu `API_TOKEN`
   - Cuerpo de la petición: `Formulario`
     - Campo `file` → tipo *Archivo* → la foto del paso 1
3. **Obtener valor del diccionario** → clave `text`.
4. **Mostrar resultado** / **Copiar al portapapeles**.

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | sí | Clave de [Google AI Studio](https://aistudio.google.com/apikey). También se acepta `GEMINI_APIKEY`. |
| `API_TOKEN` | sí | Token compartido con el Atajo. Genéralo con `openssl rand -hex 32`. |
| `GEMINI_MODEL` | no | Por defecto `gemini-3.6-flash`. |
| `MAX_UPLOAD_BYTES` | no | Por defecto `10485760` (10 MB). |
