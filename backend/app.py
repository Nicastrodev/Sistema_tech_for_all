import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from models import db

# =====================================================
# CARREGAR VARIÁVEIS DE AMBIENTE
# =====================================================
load_dotenv()


def create_app():
    """
    Cria e configura a aplicação Flask.
    O frontend multipágina está em 'static' e o backend na API centralizada 'routes/api.py'.
    """
    app = Flask(__name__, static_folder="static", static_url_path="")
    CORS(app)

    # =====================================================
    # CONFIGURAÇÕES GERAIS
    # =====================================================
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")

    # Banco de dados
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME")

    app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default_secret")

    db.init_app(app)

    # =====================================================
    # BLUEPRINTS (API)
    # =====================================================
    from routes.api import bp as api_bp
    app.register_blueprint(api_bp)

    # =====================================================
    # ROTAS DO FRONTEND (PÁGINAS HTML)
    # =====================================================
    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/dashboard/teacher")
    def serve_dashboard_teacher():
        return send_from_directory(app.static_folder, "dashboard_teacher.html")

    @app.route("/dashboard/student")
    def serve_dashboard_student():
        return send_from_directory(app.static_folder, "dashboard_student.html")

    @app.route("/create_class")
    def serve_create_class():
        return send_from_directory(app.static_folder, "create_class.html")

    @app.route("/diary")
    def serve_diary():
        return send_from_directory(app.static_folder, "diary.html")

    @app.route("/activities/teacher")
    def serve_activities_teacher():
        return send_from_directory(app.static_folder, "activities_teacher.html")

    @app.route("/activities/student")
    def serve_activities_student():
        return send_from_directory(app.static_folder, "activities_student.html")

    @app.route("/lessons")
    def serve_lessons():
        return send_from_directory(app.static_folder, "lessons.html")

    @app.route("/grades")
    def serve_grades():
        return send_from_directory(app.static_folder, "grades.html")

    @app.route("/reports")
    def serve_reports():
        return send_from_directory(app.static_folder, "reports.html")

    @app.route("/chat")
    def serve_chat():
        return send_from_directory(app.static_folder, "chat.html")

    @app.route("/turma")
    def serve_turma():
        return send_from_directory(app.static_folder, "turma.html")

    # =====================================================
    # ARQUIVOS ESTÁTICOS (CSS, JS, imagens etc.)
    # =====================================================
    @app.route("/<path:filename>")
    def serve_static_files(filename):
        """Permite servir arquivos estáticos diretamente da pasta 'static'."""
        return send_from_directory(app.static_folder, filename)

    # =====================================================
    # HEALTHCHECK
    # =====================================================
    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


# =====================================================
# EXECUÇÃO DIRETA
# =====================================================
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()  # Cria tabelas automaticamente se não existirem
    app.run(host="0.0.0.0", port=5050, debug=True)
