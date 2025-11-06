from flask import Blueprint, request, jsonify, current_app, send_from_directory
from models import db, User, Turma, AlunoTurma, Tarefa, Resposta
from werkzeug.security import check_password_hash
from calcular_notas import calcular_media_notas
from functools import wraps
from datetime import datetime
import werkzeug
import random
import string
import os

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

bp = Blueprint("api", __name__, url_prefix="/api")

# =====================================================
# FUNÇÃO AUXILIAR: OBTÉM USUÁRIO ATUAL
# =====================================================


def _get_user_by_id(user_id):
    if not user_id:
        return None
    return User.query.get(int(user_id))

# =====================================================
# DECORATOR DE PERMISSÃO
# =====================================================


def require_role(required_role):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                data = request.get_json() or {}
            except Exception:
                data = {}
            user_id = data.get("userId") or request.args.get(
                "userId") or request.headers.get("X-User-Id")
            role = data.get("role") or request.args.get(
                "role") or request.headers.get("X-User-Role")

            if not user_id or not role:
                return jsonify({"success": False, "message": "Autenticação insuficiente."}), 401

            user = _get_user_by_id(user_id)
            if not user:
                return jsonify({"success": False, "message": "Usuário não encontrado."}), 404

            if user.role != role:
                return jsonify({"success": False, "message": "Tipo de conta incorreto."}), 403
            if user.role != required_role:
                return jsonify({"success": False, "message": f"Acesso restrito a usuários do tipo '{required_role}'."}), 403

            request.current_user = user
            return f(*args, **kwargs)
        return wrapped
    return decorator


# =====================================================
# LOGIN
# =====================================================
@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    role = data.get("role")

    if not email or not password or not role:
        return jsonify({"success": False, "message": "Preencha todos os campos."}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": False, "message": "Usuário não encontrado."}), 404
    if user.role != role:
        return jsonify({"success": False, "message": "Tipo de conta incorreto."}), 403
    if not check_password_hash(user.password_hash, password):
        return jsonify({"success": False, "message": "Senha incorreta."}), 401

    return jsonify({"success": True, "role": user.role, "user_id": user.id, "name": user.name}), 200


# =====================================================
# TURMAS
# =====================================================
@bp.route("/turmas", methods=["GET"])
def listar_turmas():
    user_id = request.args.get("userId")
    role = request.args.get("role")

    try:
        if role == "teacher":
            turmas = Turma.query.filter_by(professor_id=user_id).all()
        elif role == "student":
            relacoes = AlunoTurma.query.filter_by(aluno_id=user_id).all()
            turmas = [rel.turma for rel in relacoes]
        else:
            turmas = Turma.query.all()

        return jsonify({
            "success": True,
            "turmas": [
                {
                    "id": t.id,
                    "nome": t.nome,
                    "descricao": t.descricao,
                    "codigo_acesso": t.codigo_acesso,
                    "professor_nome": getattr(t.professor, "name", None),
                    "num_alunos": t.alunos_assoc.count()
                } for t in turmas
            ]
        }), 200
    except Exception as e:
        print("Erro listar turmas:", e)
        return jsonify({"success": False, "message": "Erro interno ao listar turmas."}), 500


@bp.route("/turmas", methods=["POST"])
@require_role("teacher")
def criar_turma():
    data = request.get_json() or {}
    nome = data.get("className")
    descricao = data.get("classDesc")
    professor = request.current_user

    if not nome:
        return jsonify({"success": False, "message": "O nome da turma é obrigatório."}), 400

    try:
        codigo = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=5))
        nova_turma = Turma(nome=nome, descricao=descricao,
                           codigo_acesso=codigo, professor_id=professor.id)
        db.session.add(nova_turma)
        db.session.commit()
        return jsonify({"success": True, "codigo_acesso": codigo, "message": f"Turma '{nome}' criada!", "turma_id": nova_turma.id}), 201
    except Exception as e:
        db.session.rollback()
        print("Erro criar turma:", e)
        return jsonify({"success": False, "message": "Erro ao criar turma."}), 500


# =====================================================
# UPLOAD DE ATIVIDADE (Aluno)
# =====================================================
@bp.route("/tarefas/<int:tarefa_id>/responder", methods=["POST"])
@require_role("student")
def responder_tarefa(tarefa_id):
    aluno = request.current_user
    tarefa = Tarefa.query.get(tarefa_id)
    if not tarefa:
        return jsonify({"success": False, "message": "Tarefa não encontrada."}), 404

    if 'file' not in request.files and not request.form.get("conteudo"):
        return jsonify({"success": False, "message": "Nenhum arquivo ou conteúdo enviado."}), 400

    try:
        file = request.files.get("file")
        uploads = current_app.config.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(uploads, exist_ok=True)

        filename = None
        if file and file.filename:
            safe_name = werkzeug.utils.secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            filename = f"{tarefa_id}_{aluno.id}_{timestamp}_{safe_name}"
            file.save(os.path.join(uploads, filename))

        resposta = Resposta(tarefa_id=tarefa.id, aluno_id=aluno.id,
                            conteudo=filename or request.form.get("conteudo"))
        db.session.add(resposta)
        db.session.commit()
        return jsonify({"success": True, "message": "Envio realizado com sucesso."}), 201
    except Exception as e:
        db.session.rollback()
        print("Erro enviar resposta:", e)
        return jsonify({"success": False, "message": "Erro ao enviar a resposta."}), 500


@bp.route("/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    uploads = current_app.config.get("UPLOAD_FOLDER", "uploads")
    return send_from_directory(uploads, filename)


# =====================================================
# MATERIAIS (AULAS) - LIMPO E PRONTO PARA TESTAR
# =====================================================
@bp.route("/materiais", methods=["POST"])
@require_role("teacher")
def publicar_material():
    """
    Professor publica um novo material (aula, PDF, vídeo, etc.)
    Salva arquivo em uploads/ e registra a entrada na tabela Material.
    """
    professor = request.current_user
    titulo = request.form.get("titulo")
    descricao = request.form.get("descricao")
    file = request.files.get("arquivo")

    if not titulo:
        return jsonify({"success": False, "message": "O título é obrigatório."}), 400

    try:
        uploads = current_app.config.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(uploads, exist_ok=True)

        arquivo_path = None
        if file and file.filename:
            filename = werkzeug.utils.secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            save_name = f"{professor.id}_{timestamp}_{filename}"
            file.save(os.path.join(uploads, save_name))
            arquivo_path = save_name

        # Salva no banco usando o novo modelo Material
        from models import Material  # import local para evitar loop circular em alguns setups
        material = Material(
            titulo=titulo,
            descricao=descricao,
            arquivo=arquivo_path,
            professor_id=professor.id
        )
        db.session.add(material)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Material publicado com sucesso!",
            "material": material.to_dict(request.host_url)
        }), 201
    except Exception as e:
        db.session.rollback()
        print("Erro publicar material:", e)
        return jsonify({"success": False, "message": "Erro ao publicar material."}), 500


@bp.route("/materiais", methods=["GET"])
def listar_materiais():
    """
    Lista materiais disponíveis (ordenados por data).
    Retorna array vazio se não houver nada.
    """
    try:
        from models import Material
        materiais = Material.query.order_by(
            Material.data_publicacao.desc()).all()
        result = [m.to_dict(request.host_url) for m in materiais]
        return jsonify({"success": True, "materiais": result}), 200
    except Exception as e:
        print("Erro ao listar materiais:", e)
        return jsonify({"success": False, "message": "Erro ao listar materiais."}), 500

# =====================================================
# RELATÓRIO PDF (DASHBOARD TEACHER)
# =====================================================


@bp.route("/relatorios/turma/<int:turma_id>/pdf", methods=["GET"])
@require_role("teacher")
def gerar_relatorio_pdf(turma_id):
    professor = request.current_user
    turma = Turma.query.get(turma_id)
    if not turma:
        return jsonify({"success": False, "message": "Turma não encontrada."}), 404

    if turma.professor_id != professor.id:
        return jsonify({"success": False, "message": "Você não é o responsável por esta turma."}), 403

    try:
        alunos_assoc = turma.alunos_assoc.all()
        if not alunos_assoc:
            return jsonify({"success": False, "message": "Nenhum aluno encontrado nesta turma."}), 404

        uploads_dir = os.path.join(current_app.config.get(
            "UPLOAD_FOLDER", "uploads"), "relatorios")
        os.makedirs(uploads_dir, exist_ok=True)

        filename = f"relatorio_turma_{turma.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        filepath = os.path.join(uploads_dir, filename)

        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4

        c.setFont("Helvetica-Bold", 14)
        c.drawString(2 * cm, height - 2 * cm,
                     "Relatório Acadêmico - Tech For All")
        c.setFont("Helvetica", 11)
        c.drawString(2 * cm, height - 3 * cm, f"Turma: {turma.nome}")
        c.drawString(2 * cm, height - 3.6 * cm, f"Professor: {professor.name}")
        c.drawString(2 * cm, height - 4.2 * cm,
                     f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        data = [["Aluno", "Média", "Situação"]]
        medias, aprovados, recuperacao, reprovados = [], 0, 0, 0

        for assoc in alunos_assoc:
            aluno = User.query.get(assoc.aluno_id)
            respostas = Resposta.query.join(Tarefa).filter(
                Tarefa.turma_id == turma.id, Resposta.aluno_id == assoc.aluno_id
            ).all()
            notas = [r.nota or 0 for r in respostas]
            resultado = calcular_media_notas(notas, -1)

            media = round(resultado["media"], 2)
            situacao = resultado["situacao"]

            medias.append(media)
            if situacao == "Aprovado":
                aprovados += 1
            elif situacao == "Recuperação":
                recuperacao += 1
            else:
                reprovados += 1

            data.append(
                [aluno.name if aluno else "Aluno desconhecido", str(media), situacao])

        media_geral = round(sum(medias) / len(medias), 2) if medias else 0.0

        data.append(["", "", ""])
        data.append(["Média geral da turma", str(media_geral), ""])
        data.append(["Aprovados", str(aprovados), ""])
        data.append(["Recuperação", str(recuperacao), ""])
        data.append(["Reprovados", str(reprovados), ""])

        table = Table(data, colWidths=[9 * cm, 3 * cm, 4 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86C1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
        ]))

        table.wrapOn(c, width, height)
        table.drawOn(c, 2 * cm, height - (len(data) + 7) * 0.6 * cm)

        c.showPage()
        c.save()

        file_url = f"{request.host_url}api/uploads/relatorios/{filename}"
        return jsonify({"success": True, "message": "Relatório gerado com sucesso.", "pdf_url": file_url}), 200

    except Exception as e:
        print("Erro gerar PDF:", e)
        return jsonify({"success": False, "message": "Erro ao gerar relatório PDF."}), 500
