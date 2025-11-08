# routes/api.py
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


# --------------------
# Auxiliares
# --------------------
def _get_user_by_id(user_id):
    """Busca usuário pelo ID, aceita int/str e retorna None se inválido."""
    if user_id is None:
        return None
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


def _extract_userid_and_role_from_request():
    """
    Tenta extrair user_id e role das fontes possíveis:
    1) Headers X-User-Id / X-User-Role
    2) Query params userId / role
    3) JSON body userId / role
    Retorna tuple (user_id_or_None, role_or_None)
    """
    # 1) headers
    user_id = request.headers.get("X-User-Id")
    role = request.headers.get("X-User-Role")

    # 2) fallback query / body
    if not user_id or not role:
        data = request.get_json(silent=True) or {}
        if not user_id:
            user_id = data.get("userId") or request.args.get("userId")
        if not role:
            role = data.get("role") or request.args.get("role")

    # normalize empty strings to None
    if user_id == "":
        user_id = None
    if role == "":
        role = None

    return user_id, role


# --------------------
# Decorator: requer role
# --------------------
def require_role(required_role):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user_id, role = _extract_userid_and_role_from_request()

            if not user_id or not role:
                return jsonify({"success": False, "message": "Sem autenticação."}), 401

            user = _get_user_by_id(user_id)
            if not user:
                return jsonify({"success": False, "message": "Usuário não encontrado."}), 404
            if user.role != required_role:
                return jsonify({"success": False, "message": f"Acesso permitido apenas para '{required_role}'."}), 403

            request.current_user = user
            return f(*args, **kwargs)
        return wrapped
    return decorator


# --------------------
# Login
# --------------------
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
    if not user.check_password(password):
        return jsonify({"success": False, "message": "Senha incorreta."}), 401

    return jsonify({"success": True, "role": user.role, "user_id": user.id, "name": user.name}), 200


# ===========================
# TURMAS - criação / leitura / edição / exclusão
# ===========================

@bp.route("/turmas", methods=["POST"])
@require_role("teacher")
def criar_turma():
    """Cria uma nova turma"""
    try:
        data = request.get_json() or {}
        nome = data.get("nome")
        descricao = data.get("descricao")
        professor = request.current_user  # obtido via decorator

        if not nome:
            return jsonify({"success": False, "message": "O nome da turma é obrigatório."}), 400

        codigo_acesso = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=5))

        nova_turma = Turma(
            nome=nome,
            descricao=descricao,
            codigo_acesso=codigo_acesso,
            professor_id=professor.id
        )
        db.session.add(nova_turma)
        db.session.commit()

        print(
            f"✅ Turma criada: id={nova_turma.id}, nome='{nova_turma.nome}', professor_id={professor.id}")
        return jsonify({
            "success": True,
            "turma_id": nova_turma.id,
            "codigo_acesso": nova_turma.codigo_acesso,
            "message": f"Turma '{nome}' criada com sucesso!"
        }), 201
    except Exception as e:
        db.session.rollback()
        print("❌ Erro ao criar turma:", e)
        return jsonify({"success": False, "message": "Erro ao criar turma."}), 500


@bp.route("/turmas", methods=["GET"])
def listar_turmas():
    """Lista turmas do professor / aluno ou todas"""
    # Debug: imprimir headers/args para ajudar a diagnosticar problemas no front
    try:
        print(">>> /api/turmas request.headers:", dict(request.headers))
        print(">>> /api/turmas request.args:", request.args.to_dict())
    except Exception:
        pass

    # Extrai userId/role de headers, query ou body
    user_id_raw = request.args.get("userId") or request.headers.get(
        "X-User-Id") or (request.get_json(silent=True) or {}).get("userId")
    role = request.args.get("role") or request.headers.get(
        "X-User-Role") or (request.get_json(silent=True) or {}).get("role")

    try:
        # converte user_id para int se possível
        try:
            user_id = int(user_id_raw) if user_id_raw is not None and str(
                user_id_raw).isdigit() else None
        except Exception:
            user_id = None

        turmas = []
        if role == "teacher" and user_id:
            turmas = Turma.query.filter_by(professor_id=user_id).all()
        elif role == "student" and user_id:
            relacoes = AlunoTurma.query.filter_by(aluno_id=user_id).all()
            turmas = [rel.turma for rel in relacoes if rel.turma]
        else:
            # Se role não informada: devolve vazio (evita listar tudo por segurança)
            turmas = []

        turmas_data = []
        for t in turmas:
            try:
                turmas_data.append({
                    "id": t.id,
                    "nome": t.nome,
                    "descricao": t.descricao,
                    "codigo_acesso": t.codigo_acesso,
                    "professor_nome": getattr(t.professor, "name", None),
                    "num_alunos": t.alunos_assoc.count() if hasattr(t, "alunos_assoc") else 0
                })
            except Exception as e:
                print(
                    f"Erro processando turma {getattr(t, 'id', 'unknown')}: {e}")

        print(
            f"📘 listar_turmas -> user_id={user_id}, role={role}, count={len(turmas_data)}")
        return jsonify({"success": True, "turmas": turmas_data}), 200
    except Exception as e:
        print("❌ Erro listar turmas:", e)
        return jsonify({"success": False, "message": "Erro interno ao listar turmas."}), 500


@bp.route("/turmas/<int:turma_id>", methods=["GET"])
def obter_turma(turma_id):
    """Detalhes de uma turma"""
    try:
        turma = Turma.query.get(turma_id)
        if not turma:
            return jsonify({"success": False, "message": "Turma não encontrada."}), 404

        alunos_assoc = AlunoTurma.query.filter_by(turma_id=turma.id).all()
        total_alunos = len(alunos_assoc)

        respostas = Resposta.query.join(Tarefa, Tarefa.id == Resposta.tarefa_id).filter(
            Tarefa.turma_id == turma.id).all()
        notas = [r.nota for r in respostas if r.nota is not None]
        media_geral = round(sum(notas) / len(notas), 1) if notas else 0.0

        frequencias = [a.frequencia for a in alunos_assoc if getattr(
            a, "frequencia", None) is not None]
        freq_media = round(sum(frequencias) / len(frequencias),
                           1) if frequencias else 100.0

        turma_data = {
            "id": turma.id,
            "nome": turma.nome,
            "descricao": turma.descricao,
            "codigo_acesso": turma.codigo_acesso,
            "professor_nome": getattr(turma.professor, "name", "Desconhecido"),
            "total_alunos": total_alunos,
            "media_geral": media_geral,
            "frequencia_media": freq_media
        }
        return jsonify({"success": True, "turma": turma_data}), 200
    except Exception as e:
        print("Erro ao obter turma:", e)
        return jsonify({"success": False, "message": "Erro ao carregar turma."}), 500


@bp.route("/turmas/entrar", methods=["POST"])
@require_role("student")
def entrar_turma():
    """Aluno entra em turma usando código de acesso"""
    try:
        aluno = request.current_user
        data = request.get_json() or {}
        codigo = (data.get("codigo_acesso") or data.get(
            "codigo") or data.get("code") or "").upper()
        if not codigo:
            return jsonify({"success": False, "message": "Código é obrigatório."}), 400

        turma = Turma.query.filter_by(codigo_acesso=codigo).first()
        if not turma:
            return jsonify({"success": False, "message": "Turma não encontrada."}), 404

        existe = AlunoTurma.query.filter_by(
            aluno_id=aluno.id, turma_id=turma.id).first()
        if existe:
            return jsonify({"success": False, "message": "Você já está nessa turma."}), 400

        assoc = AlunoTurma(aluno_id=aluno.id, turma_id=turma.id)
        db.session.add(assoc)
        db.session.commit()
        return jsonify({"success": True, "message": f"Você entrou na turma '{turma.nome}' com sucesso!", "turma_id": turma.id}), 200
    except Exception as e:
        db.session.rollback()
        print("Erro entrar turma:", e)
        return jsonify({"success": False, "message": "Erro ao entrar na turma."}), 500


@bp.route("/turmas/<int:turma_id>/adicionar_aluno", methods=["POST"])
@require_role("teacher")
def adicionar_aluno(turma_id):
    try:
        turma = Turma.query.get(turma_id)
        if not turma:
            return jsonify({"success": False, "message": "Turma não encontrada."}), 404

        data = request.get_json() or {}
        aluno_id = data.get("aluno_id") or data.get("alunoId")
        aluno = User.query.get(aluno_id)
        if not aluno or aluno.role != "student":
            return jsonify({"success": False, "message": "Aluno inválido."}), 400

        existe = AlunoTurma.query.filter_by(
            aluno_id=aluno.id, turma_id=turma.id).first()
        if existe:
            return jsonify({"success": False, "message": "Aluno já está na turma."}), 400

        novo = AlunoTurma(aluno_id=aluno.id, turma_id=turma.id)
        db.session.add(novo)
        db.session.commit()
        return jsonify({"success": True, "message": "Aluno adicionado!"}), 200
    except Exception as e:
        db.session.rollback()
        print("Erro adicionar aluno:", e)
        return jsonify({"success": False, "message": "Erro ao adicionar aluno."}), 500


@bp.route("/turmas/<int:turma_id>", methods=["PUT"])
@require_role("teacher")
def editar_turma(turma_id):
    try:
        turma = Turma.query.get(turma_id)
        if not turma:
            return jsonify({"success": False, "message": "Turma não encontrada."}), 404

        if turma.professor_id != request.current_user.id:
            return jsonify({"success": False, "message": "Acesso negado."}), 403

        data = request.get_json() or {}
        turma.nome = data.get("nome", turma.nome)
        turma.descricao = data.get("descricao", turma.descricao)
        db.session.commit()
        return jsonify({"success": True, "message": "Turma atualizada."}), 200
    except Exception as e:
        db.session.rollback()
        print("Erro editar turma:", e)
        return jsonify({"success": False, "message": "Erro ao editar turma."}), 500


@bp.route("/turmas/<int:turma_id>", methods=["DELETE"])
@require_role("teacher")
def deletar_turma(turma_id):
    try:
        turma = Turma.query.get(turma_id)
        if not turma:
            return jsonify({"success": False, "message": "Turma não encontrada."}), 404

        if turma.professor_id != request.current_user.id:
            return jsonify({"success": False, "message": "Acesso negado."}), 403

        # Deletar associações, respostas e tarefas antes (cascata)
        AlunoTurma.query.filter_by(turma_id=turma.id).delete()
        tarefas_ids = [t.id for t in Tarefa.query.filter_by(
            turma_id=turma.id).all()]
        if tarefas_ids:
            Resposta.query.filter(Resposta.tarefa_id.in_(
                tarefas_ids)).delete(synchronize_session=False)
            Tarefa.query.filter_by(turma_id=turma.id).delete()

        db.session.delete(turma)
        db.session.commit()
        return jsonify({"success": True, "message": "Turma excluída."}), 200
    except Exception as e:
        db.session.rollback()
        print("Erro deletar turma:", e)
        return jsonify({"success": False, "message": "Erro ao excluir turma."}), 500


@bp.route("/turmas/<int:turma_id>/aluno/<int:aluno_id>", methods=["DELETE"])
@require_role("teacher")
def remover_aluno(turma_id, aluno_id):
    try:
        turma = Turma.query.get(turma_id)
        if not turma or turma.professor_id != request.current_user.id:
            return jsonify({"success": False, "message": "Acesso negado."}), 403

        rel = AlunoTurma.query.filter_by(
            turma_id=turma_id, aluno_id=aluno_id).first()
        if not rel:
            return jsonify({"success": False, "message": "Aluno não encontrado na turma."}), 404

        db.session.delete(rel)
        db.session.commit()
        return jsonify({"success": True, "message": "Aluno removido."}), 200
    except Exception as e:
        db.session.rollback()
        print("Erro remover aluno:", e)
        return jsonify({"success": False, "message": "Erro ao remover aluno."}), 500


# ===========================
# TAREFAS / RESPOSTAS / UPLOADS
# ===========================
@bp.route("/tarefas", methods=["POST"])
@require_role("teacher")
def criar_tarefa():
    try:
        data = request.get_json() or {}
        titulo = data.get("titulo")
        descricao = data.get("descricao")
        prazo = data.get("prazo")
        turma_id = data.get("turma_id")
        professor = request.current_user

        if not titulo or not prazo or not turma_id:
            return jsonify({"success": False, "message": "Turma, título e prazo são obrigatórios."}), 400

        turma = Turma.query.get(turma_id)
        if not turma or turma.professor_id != professor.id:
            return jsonify({"success": False, "message": "Turma inválida ou não pertence a você."}), 403

        nova = Tarefa(
            titulo=titulo,
            descricao=descricao,
            data_entrega=datetime.strptime(prazo, "%Y-%m-%d").date(),
            turma_id=turma_id,
            criado_por=professor.id
        )
        db.session.add(nova)
        db.session.commit()
        return jsonify({"success": True, "message": "Atividade publicada!", "tarefa_id": nova.id}), 201
    except Exception as e:
        db.session.rollback()
        print("Erro criar tarefa:", e)
        return jsonify({"success": False, "message": "Erro ao criar tarefa."}), 500


@bp.route("/tarefas", methods=["GET"])
def listar_tarefas():
    user_id_raw = request.args.get("userId") or request.headers.get(
        "X-User-Id") or (request.get_json(silent=True) or {}).get("userId")
    role = request.args.get("role") or request.headers.get(
        "X-User-Role") or (request.get_json(silent=True) or {}).get("role")

    try:
        try:
            user_id = int(user_id_raw) if user_id_raw is not None and str(
                user_id_raw).isdigit() else None
        except Exception:
            user_id = None

        if not user_id or not role:
            return jsonify({"success": False, "message": "Autenticação necessária."}), 401

        if role == "teacher":
            tarefas = Tarefa.query.filter_by(criado_por=user_id).order_by(
                Tarefa.data_entrega.desc()).all()
        elif role == "student":
            turmas_aluno_ids = [
                assoc.turma_id for assoc in AlunoTurma.query.filter_by(aluno_id=user_id).all()]
            if not turmas_aluno_ids:
                return jsonify({"success": True, "tarefas": []}), 200
            tarefas = Tarefa.query.filter(Tarefa.turma_id.in_(
                turmas_aluno_ids)).order_by(Tarefa.data_entrega.desc()).all()
        else:
            return jsonify({"success": False, "message": "Função desconhecida."}), 400

        tarefas_data = [{"id": t.id, "titulo": t.titulo, "descricao": t.descricao,
                         "prazo": t.data_entrega.isoformat() if t.data_entrega else None} for t in tarefas]
        return jsonify({"success": True, "tarefas": tarefas_data}), 200
    except Exception as e:
        print("Erro listar tarefas:", e)
        return jsonify({"success": False, "message": "Erro ao listar tarefas."}), 500


@bp.route("/tarefas/<int:tarefa_id>/responder", methods=["POST"])
@require_role("student")
def responder_tarefa(tarefa_id):
    aluno = request.current_user
    tarefa = Tarefa.query.get(tarefa_id)
    if not tarefa:
        return jsonify({"success": False, "message": "Tarefa não encontrada."}), 404

    assoc = AlunoTurma.query.filter_by(
        aluno_id=aluno.id, turma_id=tarefa.turma_id).first()
    if not assoc:
        return jsonify({"success": False, "message": "Você não pertence à turma desta atividade."}), 403

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
            filename = f"T{tarefa_id}_A{aluno.id}_{timestamp}_{safe_name}"
            file.save(os.path.join(uploads, filename))

        conteudo_resposta = filename or request.form.get("conteudo")
        resposta = Resposta.query.filter_by(
            tarefa_id=tarefa.id, aluno_id=aluno.id).first()
        if not resposta:
            resposta = Resposta(tarefa_id=tarefa.id, aluno_id=aluno.id)
            db.session.add(resposta)

        resposta.conteudo = conteudo_resposta
        resposta.enviado_em = datetime.utcnow()
        db.session.commit()
        return jsonify({"success": True, "message": "Envio realizado com sucesso.", "resposta_id": resposta.id}), 201
    except Exception as e:
        db.session.rollback()
        print("Erro ao salvar resposta:", e)
        return jsonify({"success": False, "message": "Erro ao enviar a resposta."}), 500


@bp.route("/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    uploads = current_app.config.get("UPLOAD_FOLDER", "uploads")
    if "relatorio_" in filename:
        return send_from_directory(os.path.join(uploads, "relatorios"), filename)
    return send_from_directory(uploads, filename)


@bp.route("/tarefas/entregas", methods=["GET"])
@require_role("teacher")
def listar_entregas():
    professor = request.current_user
    try:
        tarefas_ids = [t.id for t in Tarefa.query.filter_by(
            criado_por=professor.id).all()]
        if not tarefas_ids:
            return jsonify({"success": True, "entregas": []}), 200

        respostas = Resposta.query.filter(Resposta.tarefa_id.in_(
            tarefas_ids)).order_by(Resposta.enviado_em.desc()).all()
        entregas = []
        for r in respostas:
            aluno = User.query.get(r.aluno_id)
            tarefa = Tarefa.query.get(r.tarefa_id)
            arquivo_nome = os.path.basename(r.conteudo) if r.conteudo else None
            arquivo_url = f"{request.host_url}api/uploads/{arquivo_nome}" if arquivo_nome else None
            entregas.append({
                "id": r.id,
                "aluno_nome": aluno.name if aluno else "Aluno desconhecido",
                "tarefa_titulo": tarefa.titulo if tarefa else None,
                "arquivo_nome": arquivo_nome,
                "arquivo_url": arquivo_url,
                "data_envio": r.enviado_em.isoformat() if r.enviado_em else None,
                "nota": r.nota
            })
        return jsonify({"success": True, "entregas": entregas}), 200
    except Exception as e:
        print("Erro listar entregas:", e)
        return jsonify({"success": False, "message": "Erro ao listar entregas."}), 500


@bp.route("/tarefas/<int:resposta_id>/avaliar", methods=["POST"])
@require_role("teacher")
def avaliar_resposta(resposta_id):
    professor = request.current_user
    data = request.get_json() or {}
    nota = data.get("nota")
    if nota is None:
        return jsonify({"success": False, "message": "Nota obrigatória."}), 400

    resposta = Resposta.query.get(resposta_id)
    if not resposta:
        return jsonify({"success": False, "message": "Resposta não encontrada."}), 404

    tarefa = Tarefa.query.get(resposta.tarefa_id)
    if not tarefa or tarefa.criado_por != professor.id:
        return jsonify({"success": False, "message": "Acesso negado."}), 403

    try:
        resposta.nota = float(nota)
        db.session.commit()

        turma_id = tarefa.turma_id
        respostas_aluno_turma = Resposta.query.join(Tarefa).filter(
            Resposta.aluno_id == resposta.aluno_id, Tarefa.turma_id == turma_id).all()

        notas = [r.nota for r in respostas_aluno_turma if r.nota is not None]
        resultado = calcular_media_notas(notas, -1)
        media = resultado.get("media", 0.0)

        aluno_assoc = AlunoTurma.query.filter_by(
            aluno_id=resposta.aluno_id, turma_id=turma_id).first()
        if aluno_assoc:
            aluno_assoc.media = media
            db.session.commit()

        return jsonify({"success": True, "message": "Nota registrada.", "media_atual": media}), 200
    except Exception as e:
        db.session.rollback()
        print("Erro avaliar:", e)
        return jsonify({"success": False, "message": "Erro ao atribuir nota."}), 500


# ===========================
# MATERIAIS
# ===========================
@bp.route("/materiais", methods=["POST"])
@require_role("teacher")
def publicar_material():
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
            save_name = f"M_{professor.id}_{timestamp}_{filename}"
            file.save(os.path.join(uploads, save_name))
            arquivo_path = save_name

        from models import Material
        material = Material(titulo=titulo, descricao=descricao,
                            arquivo=arquivo_path, professor_id=professor.id)
        db.session.add(material)
        db.session.commit()

        try:
            material_data = material.to_dict(request.host_url)
        except Exception:
            material_data = {"id": material.id,
                             "titulo": material.titulo, "arquivo": arquivo_path}

        return jsonify({"success": True, "message": "Material publicado com sucesso!", "material": material_data}), 201
    except Exception as e:
        db.session.rollback()
        print("Erro publicar material:", e)
        return jsonify({"success": False, "message": "Erro ao publicar material."}), 500


@bp.route("/materiais", methods=["GET"])
def listar_materiais():
    try:
        from models import Material
        materiais = Material.query.order_by(
            Material.data_publicacao.desc()).all()
        result = []
        for m in materiais:
            try:
                result.append(m.to_dict(request.host_url))
            except Exception:
                result.append(
                    {"id": m.id, "titulo": m.titulo, "arquivo": m.arquivo})
        return jsonify({"success": True, "materiais": result}), 200
    except Exception as e:
        print("Erro ao listar materiais:", e)
        return jsonify({"success": False, "message": "Erro ao listar materiais."}), 500


# ===========================
# RELATÓRIO PDF
# ===========================
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
        medias = []
        aprovados = recuperacao = reprovados = 0

        for assoc in alunos_assoc:
            aluno = User.query.get(assoc.aluno_id)
            respostas = Resposta.query.join(Tarefa).filter(
                Tarefa.turma_id == turma.id, Resposta.aluno_id == assoc.aluno_id).all()
            notas = [r.nota for r in respostas if r.nota is not None]

            resultado = calcular_media_notas(notas, -1)
            media = round(resultado.get("media", 0.0), 2)
            situacao = resultado.get("situacao", "Sem notas")

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

        file_url = f"{request.host_url}api/uploads/{filename}"
        return jsonify({"success": True, "message": "Relatório gerado com sucesso.", "pdf_url": file_url}), 200
    except Exception as e:
        print("Erro gerar PDF:", e)
        return jsonify({"success": False, "message": "Erro ao gerar relatório PDF."}), 500
