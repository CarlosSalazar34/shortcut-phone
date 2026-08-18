from flask import Flask, jsonify, request
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({
        "message": "api arriba. ✅",
        "time": datetime.now(timezone.utc)
    })

@app.route("/scan/image")
def process_image():
    if "file" not in request.files:
        return jsonify({
            "error": "No se subio ningun archivo. ❌"
        })
    file = request.files["file"]
    if file.filename == "":
        return jsonify({
            "error": "Entidad no reconocida. 🤖"
        })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")