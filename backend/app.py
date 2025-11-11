import os
import urllib.parse
from flask import Flask, send_from_directory, redirect, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from models import db, Turma, AlunoTurma

# =====================================================
# CARREGAR VARIÁVEIS DE AMBIENTE
# =====================================================
load_dotenv()


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")
    CORS(app)

    # =====================================================
    # CONFIGURAÇÕES GERAIS
    # =====================================================
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")

    # =====================================================
    # BANCO DE DADOS (Aiven / Render)
    # =====================================================
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        # Monta manualmente caso use DB_* variáveis
        user = os.getenv("DB_USER")
        password = urllib.parse.quote_plus(os.getenv("DB_PASS", ""))
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT", "3306")
        name = os.getenv("DB_NAME")

        if user and host and name:
            database_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?ssl=true"

    if not database_url:
        print("❌ ERRO: Nenhuma URL de banco encontrada. Configure DATABASE_URL no Render.")
    else:
        # Oculta a senha no log
        safe_url = database_url
        if "@" in safe_url:
            left, right = safe_url.split("@", 1)
            if ":" in left:
                u, _ = left.split(":", 1)
                safe_url = f"{u}:****@{right}"
        print(f"✅ DATABASE_URL detectada: {safe_url}")

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default_secret")

    db.init_app(app)

    # =====================================================
    # BLUEPRINTS (API)
    # =====================================================
    from routes.api import bp as api_bp
    app.register_blueprint(api_bp)

    # =====================================================
    # ROTA EXTRA: ENTRAR EM TURMA (para alunos)
    # =====================================================
    @app.route("/api/turmas/entrar", methods=["POST"])
    def entrar_turma():
        from models import Turma, TurmaAluno
        user_id = request.headers.get("X-User-Id")
        role = request.headers.get("X-User-Role")
        data = request.get_json() or {}
        codigo = data.get("codigo_acesso")

        if not user_id or not role:
            return jsonify({"success": False, "message": "Usuário não autenticado."}), 403

        if role != "student":
            return jsonify({"success": False, "message": "Apenas alunos podem entrar em turmas."}), 403

        if not codigo:
            return jsonify({"success": False, "message": "Código de turma não informado."}), 400

        turma = Turma.query.filter_by(codigo_acesso=codigo).first()
        if not turma:
            return jsonify({"success": False, "message": "Código de turma inválido."}), 404

        ja_existe = TurmaAluno.query.filter_by(
            aluno_id=user_id, turma_id=turma.id).first()
        if ja_existe:
            return jsonify({"success": False, "message": "Você já está nesta turma."}), 400

        nova_relacao = TurmaAluno(aluno_id=user_id, turma_id=turma.id)
        db.session.add(nova_relacao)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Você entrou na turma '{turma.nome}' com sucesso!",
            "turma": {"id": turma.id, "nome": turma.nome}
        }), 200

    # =====================================================
    # ROTAS DO FRONTEND (HTML)
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
    @app.route("/activities_student")
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
    # REDIRECIONAMENTOS AUTOMÁTICOS (.html → rota correta)
    # =====================================================
    @app.route("/<page>.html")
    def redirect_html(page):
        """Redireciona URLs com .html para a rota correta."""
        return redirect(f"/{page}")

    @app.route("/dashboard_teacher.html")
    def redirect_dashboard_teacher():
        return redirect("/dashboard/teacher")

    @app.route("/dashboard_student.html")
    def redirect_dashboard_student():
        return redirect("/dashboard/student")

    # =====================================================
    # SERVIR ARQUIVOS ESTÁTICOS (CSS, JS, imagens etc.)
    # =====================================================
    @app.route("/<path:filename>")
    def serve_static_files(filename):
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
        try:
            db.create_all()
            print("✅ Tabelas verificadas/criadas com sucesso.")
        except Exception as e:
            print(f"❌ Erro ao criar tabelas: {e}")

    port = int(os.environ.get("PORT", 5050))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
