# app.py
from flask import Flask, Blueprint, request, jsonify, current_app
from flasgger import Swagger
from werkzeug.utils import secure_filename
from pathlib import Path
import logging
import os
import requests
from typing import Optional

# -------------------------
# Configuración
# -------------------------
class Config:
    UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", "uploads"))
    ALLOWED_EXTENSIONS = {"csv"}
    N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "https://camiloan11.app.n8n.cloud/webhook-test/csv-upload")
    SWAGGER_CONFIG = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec_1",
                "route": "/apispec_1.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/"
    }

# -------------------------
# Servicio responsable de la lógica de archivos
# -------------------------
class UploadService:
    def __init__(self, upload_folder: Path, webhook_url: str, http_session: Optional[requests.Session] = None):
        self.upload_folder = Path(upload_folder)
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        self.webhook_url = webhook_url
        self.session = http_session or requests.Session()

    @staticmethod
    def allowed(filename: str, allowed_exts: set) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_exts

    def save(self, file_storage, filename: str) -> Path:
        path = self.upload_folder / filename
        file_storage.save(path)
        return path

    def forward_to_n8n(self, file_path: Path, filename: str, extra_data: dict) -> requests.Response:
        with file_path.open("rb") as f:
            files = {"file": (filename, f, "text/csv")}
            return self.session.post(self.webhook_url, files=files, data=extra_data, timeout=30)

# -------------------------
# Blueprint / rutas
# -------------------------
upload_bp = Blueprint("upload", __name__)

@upload_bp.route("/upload", methods=["POST"])
def upload_file():
    """
    Subir archivo CSV y reenviarlo automáticamente al webhook de n8n
    ---
    tags:
      - CSV
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: Selecciona el archivo CSV a subir
    responses:
      200:
        description: Archivo subido y reenviado correctamente
      400:
        description: Error en la solicitud (archivo faltante o inválido)
      502:
        description: Error al reenviar a n8n
    """
    if "file" not in request.files:
        return jsonify({"error": "No se encontró archivo en la solicitud"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    filename = secure_filename(file.filename)
    cfg = current_app.config_obj  # configuraciones pasadas al crear la app
    if not UploadService.allowed(filename, cfg.ALLOWED_EXTENSIONS):
        return jsonify({"error": "Tipo de archivo no permitido. Solo CSV."}), 400

    try:
        service: UploadService = current_app.upload_service
        saved_path = service.save(file, filename)

        # Datos adicionales que se envían a n8n (ejemplo)
        extra = {"table": "nombre_tabla_destino", "sessionId": "test-session-001"}
        response = service.forward_to_n8n(saved_path, filename, extra)

        if not response.ok:
            current_app.logger.warning("n8n responded with status %s: %s", response.status_code, response.text)
            return jsonify({
                "mensaje": "Archivo guardado localmente pero error al reenviar a n8n",
                "nombre_archivo": filename,
                "ruta_local": str(saved_path),
                "status_n8n": response.status_code,
                "respuesta_n8n": response.text
            }), 502

        return jsonify({
            "mensaje": "Archivo subido localmente y reenviado a n8n ✅",
            "nombre_archivo": filename,
            "ruta_local": str(saved_path),
            "status_n8n": response.status_code,
            "respuesta_n8n": response.text
        }), 200

    except requests.RequestException as exc:
        current_app.logger.exception("Error al conectar con n8n: %s", exc)
        return jsonify({"error": "Error al comunicarse con n8n", "detalle": str(exc)}), 502
    except Exception as exc:
        current_app.logger.exception("Error inesperado: %s", exc)
        return jsonify({"error": "Error interno del servidor", "detalle": str(exc)}), 500

# -------------------------
# Factory de la aplicación
# -------------------------
def create_app(config: Config = Config()) -> Flask:
    app = Flask(__name__)
    app.config_obj = config  # objeto de configuración accesible
    app.config.update(vars(config))
    app.logger.setLevel(logging.INFO)

    # Inicializar Swagger
    Swagger(app, config=config.SWAGGER_CONFIG)

    # Instanciar servicios e inyectarlos en la app (simple DI)
    app.upload_service = UploadService(config.UPLOAD_FOLDER, config.N8N_WEBHOOK_URL)

    # Registrar blueprints
    app.register_blueprint(upload_bp)

    return app

# -------------------------
# Punto de entrada
# -------------------------
if __name__ == "__main__":
    # En producción, preferir usar variables de entorno y un WSGI server (gunicorn/uvicorn)
    application = create_app()
    application.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
