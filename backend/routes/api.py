# routes/api.py
from flask import Blueprint, request, jsonify, send_from_directory
from models import db, User, Turma, AlunoTurma, Tarefa, Resposta
from datetime import datetime
import os
import random
import string
import traceback

bp = Blueprint("api", __name__, url_prefix="/api")

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =====================================================
# AUXILIARES
# =====================================================


def _get_user_by_id(user_id):
    if not user_id:
        return None
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


def _extract_userid_and_role_from_request():
    user_id = request.headers.get("X-User-Id")
    role = request.headers.get("X-User-Role")

    if not user_id or not role:
        data = request.get_json(silent=True) or {}
        user_id = user_id or request.args.get("userId") or data.get("userId")
        role = role or request.args.get("role") or data.get("role")

    if user_id == "":
        user_id = None
    if role == "":
        role = None
    if role:
        role = role.lower().strip()

    return user_id, role


def save_uploaded_file(file):
    """Salva o arquivo e retorna o nome gerado"""
    if not file:
        return None
    safe_name = file.filename.replace(" ", "_")
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return filename


def _json_error(message, status=500):
    return jsonify({"success": False, "message": message}), status


# =====================================================
# LOGIN
# =====================================================
@bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json() or {}
        email = data.get("email")
        password = data.get("password")
        role = (data.get("role") or "").lower()

        if not email or not password or not role:
            return _json_error("Preencha todos os campos.", 400)

        user = User.query.filter_by(email=email).first()
        if not user:
            return _json_error("Usuário não encontrado.", 404)
        if user.role.lower() != role:
            return _json_error("Tipo de conta incorreto.", 403)
        if not user.check_password(password):
            return _json_error("Senha incorreta.", 401)

        return jsonify({
            "success": True,
            "role": user.role,
            "user_id": user.id,
            "name": user.name
        }), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro interno ao processar login.")


# =====================================================
# TURMAS
# =====================================================
@bp.route("/turmas", methods=["GET"])
def listar_turmas():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user:
            return _json_error("Usuário não autenticado.", 403)

        turmas = []
        if role == "teacher":
            turmas = Turma.query.filter_by(professor_id=user.id).all()
        elif role == "student":
            relacoes = AlunoTurma.query.filter_by(aluno_id=user.id).all()
            turmas = [r.turma for r in relacoes if r.turma]

        turmas_data = []
        for t in turmas:
            total_tarefas = Tarefa.query.filter_by(turma_id=t.id).count()
            turmas_data.append({
                "id": t.id,
                "nome": t.nome,
                "descricao": t.descricao,
                "codigo_acesso": t.codigo_acesso,
                "professor_nome": getattr(t.professor, "name", None),
                "quantidade_atividades": total_tarefas
            })

        return jsonify({"success": True, "turmas": turmas_data}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao listar turmas.")

    # =====================================================
# ATUALIZAR TURMA (EDITAR)
# =====================================================


@bp.route("/turmas/<int:turma_id>", methods=["PUT"])
def atualizar_turma(turma_id):
    """
    Atualiza nome e descrição de uma turma existente.
    Somente o professor que criou a turma pode editá-la.
    """
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)

        if not user or role != "teacher":
            return _json_error("Apenas professores podem editar turmas.", 403)

        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)

        # Verifica se o professor é o dono da turma
        if turma.professor_id != user.id:
            return _json_error("Você não tem permissão para editar esta turma.", 403)

        data = request.get_json() or {}
        nome = data.get("nome", "").strip()
        descricao = data.get("descricao", "").strip()

        if not nome:
            return _json_error("O nome da turma é obrigatório.", 400)

        turma.nome = nome
        turma.descricao = descricao

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Turma atualizada com sucesso!",
            "turma": {
                "id": turma.id,
                "nome": turma.nome,
                "descricao": turma.descricao,
                "codigo_acesso": turma.codigo_acesso
            }
        }), 200

    except Exception as e:
        traceback.print_exc()
        return _json_error("Erro ao atualizar turma.")

# =====================================================
# EXCLUIR TURMA (professor)
# =====================================================


@bp.route("/turmas/<int:turma_id>", methods=["DELETE"])
def excluir_turma(turma_id):
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)

        if not user or role != "teacher":
            return _json_error("Apenas professores podem excluir turmas.", 403)

        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)

        # garantir que o professor dono da turma é quem está excluindo
        if turma.professor_id != user.id:
            return _json_error("Você não tem permissão para excluir esta turma.", 403)

        # excluir todas as relações e tarefas associadas antes da turma
        AlunoTurma.query.filter_by(turma_id=turma.id).delete()
        tarefas = Tarefa.query.filter_by(turma_id=turma.id).all()
        for tarefa in tarefas:
            # excluir respostas associadas
            Resposta.query.filter_by(tarefa_id=tarefa.id).delete()
            db.session.delete(tarefa)

        db.session.delete(turma)
        db.session.commit()

        return jsonify({"success": True, "message": "Turma excluída com sucesso!"}), 200

    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao excluir turma.")


@bp.route("/turmas/entrar", methods=["POST"])
def entrar_turma():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        data = request.get_json() or {}
        codigo = (data.get("codigo") or data.get(
            "codigo_acesso") or "").strip().upper()

        if not user_id or not role:
            return _json_error("Usuário não autenticado.", 403)

        if role != "student":
            return _json_error("Apenas alunos podem entrar em turmas.", 403)

        if not codigo:
            return _json_error("O código de acesso é obrigatório.", 400)

        aluno = _get_user_by_id(user_id)
        if not aluno:
            return _json_error("Aluno não encontrado.", 404)

        turma = Turma.query.filter_by(codigo_acesso=codigo).first()
        if not turma:
            return _json_error("Código de turma inválido.", 404)

        # Verifica se o aluno já está nessa turma
        if AlunoTurma.query.filter_by(aluno_id=aluno.id, turma_id=turma.id).first():
            return jsonify({"success": False, "message": "Você já está nessa turma."}), 400

        # Cria o vínculo aluno-turma
        nova_relacao = AlunoTurma(aluno_id=aluno.id, turma_id=turma.id)
        db.session.add(nova_relacao)
        db.session.commit()

        # Coleta alunos atualizados
        relacoes = AlunoTurma.query.filter_by(turma_id=turma.id).all()
        alunos_data = []
        for rel in relacoes:
            al = User.query.get(rel.aluno_id)
            if al:
                alunos_data.append({
                    "id": al.id,
                    "nome": al.name,
                    "email": al.email
                })

        return jsonify({
            "success": True,
            "message": f"Você entrou na turma '{turma.nome}' com sucesso!",
            "turma": {
                "id": turma.id,
                "nome": turma.nome,
                "codigo": turma.codigo_acesso,
                "descricao": turma.descricao
            },
            "alunos": alunos_data
        }), 200

    except Exception:
        traceback.print_exc()
        return _json_error("Erro interno ao entrar na turma.")

# =====================================================
# DETALHES DA TURMA (USADO NA PÁGINA /turma)
# =====================================================


@bp.route("/turmas/<int:turma_id>", methods=["GET"])
def obter_turma(turma_id):
    try:
        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)

        # alunos da turma
        alunos_rel = AlunoTurma.query.filter_by(turma_id=turma.id).all()
        total_alunos = len(alunos_rel)

        # média geral das notas dessa turma
        respostas = (
            Resposta.query.join(Tarefa, Tarefa.id == Resposta.tarefa_id)
            .filter(Tarefa.turma_id == turma.id, Resposta.nota != None)
            .all()
        )
        notas = [r.nota for r in respostas if r.nota is not None]
        media_geral = round(sum(notas) / len(notas), 1) if notas else 0.0

        # contar atividades da turma
        total_tarefas = Tarefa.query.filter_by(turma_id=turma.id).count()

        # lista completa dos alunos
        alunos_data = []
        for rel in alunos_rel:
            aluno = User.query.get(rel.aluno_id)
            if aluno:
                alunos_data.append({
                    "id": aluno.id,
                    "nome": aluno.name,
                    "email": aluno.email,
                    "data_entrada": rel.created_at.isoformat() if hasattr(rel, "created_at") else None
                })

        # 🔹 estrutura JSON compatível com o frontend antigo
        return jsonify({
            "success": True,
            "turma": {
                "id": turma.id,
                "nome": turma.nome,
                "descricao": turma.descricao,
                "codigo_acesso": turma.codigo_acesso,
                "professor_nome": getattr(turma.professor, "name", "Desconhecido"),
                "total_alunos": total_alunos,
                "media_geral": media_geral,
                "total_tarefas": total_tarefas
            },
            "alunos": alunos_data   # <-- fora de "turma" para o front encontrar
        }), 200

    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao carregar detalhes da turma.")

   # =====================================================
# LISTAR ALUNOS DE UMA TURMA (painel do professor ou aluno)
# =====================================================


@bp.route("/turmas/<int:turma_id>/alunos", methods=["GET"])
def listar_alunos_turma(turma_id):
    try:
        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)

        relacoes = AlunoTurma.query.filter_by(turma_id=turma_id).all()
        alunos_data = []

        for rel in relacoes:
            aluno = User.query.get(rel.aluno_id)
            if not aluno:
                continue

            # Calcula média das notas do aluno nesta turma
            respostas = (
                Resposta.query.join(Tarefa, Tarefa.id == Resposta.tarefa_id)
                .filter(
                    Tarefa.turma_id == turma_id,
                    Resposta.aluno_id == aluno.id,
                    Resposta.nota.isnot(None)
                )
                .all()
            )
            notas = [r.nota for r in respostas if r.nota is not None]
            media = round(sum(notas) / len(notas), 1) if notas else 0.0

            alunos_data.append({
                "id": aluno.id,
                "nome": aluno.name,
                "email": aluno.email,
                "media": media,
                "frequencia": 0  # placeholder até a presença ser implementada
            })

        return jsonify({"success": True, "alunos": alunos_data}), 200

    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao listar alunos da turma.")

# =====================================================
# TAREFAS / ATIVIDADES
# =====================================================


@bp.route("/tarefas", methods=["POST"])
def criar_tarefa():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user or role != "teacher":
            return _json_error("Apenas professores podem criar atividades.", 403)

        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        prazo = request.form.get("prazo")
        turma_id = request.form.get("turma_id")
        link = request.form.get("link")
        arquivo = request.files.get("arquivo")

        if not titulo or not turma_id:
            return _json_error("Título e turma são obrigatórios.", 400)

        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)

        filename = save_uploaded_file(arquivo) if arquivo else None

        tarefa = Tarefa(
            titulo=titulo,
            descricao=descricao,
            data_entrega=datetime.strptime(
                prazo, "%Y-%m-%d") if prazo else None,
            turma_id=turma.id,
            criado_por=user.id,
            link=link,
            arquivo=filename
        )

        db.session.add(tarefa)
        db.session.commit()

        return jsonify({"success": True, "message": "Atividade criada com sucesso!"}), 201
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao criar atividade.")


# =====================================================
# ENVIO DE RESPOSTA (ALUNO)
# =====================================================
@bp.route("/tarefas/<int:tarefa_id>/responder", methods=["POST"])
def responder_tarefa(tarefa_id):
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user or role != "student":
            return _json_error("Apenas alunos podem enviar respostas.", 403)

        tarefa = Tarefa.query.get(tarefa_id)
        if not tarefa:
            return _json_error("Atividade não encontrada.", 404)

        arquivo = request.files.get("arquivo")
        comentario = request.form.get("comentario", "")

        if not arquivo and not comentario:
            return _json_error("Envie um arquivo ou comentário.", 400)

        filename = save_uploaded_file(arquivo) if arquivo else None

        resposta = Resposta.query.filter_by(
            tarefa_id=tarefa.id, aluno_id=user.id).first()
        if not resposta:
            resposta = Resposta(tarefa_id=tarefa.id, aluno_id=user.id)

        resposta.conteudo = filename or ""
        resposta.comentario = comentario
        resposta.enviado_em = datetime.utcnow()

        db.session.add(resposta)
        db.session.commit()

        return jsonify({"success": True, "message": "Atividade enviada com sucesso!"}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao enviar atividade.")


# =====================================================
# PROFESSOR AVALIA RESPOSTAS
# =====================================================
@bp.route("/tarefas/<int:resposta_id>/avaliar", methods=["POST"])
def avaliar_entrega(resposta_id):
    try:
        user_id, role = _extract_userid_and_role_from_request()
        if role != "teacher":
            return _json_error("Apenas professores podem avaliar.", 403)

        data = request.get_json() or {}
        nota = data.get("nota")
        if nota is None:
            return _json_error("Nota é obrigatória.", 400)

        resposta = Resposta.query.get(resposta_id)
        if not resposta:
            return _json_error("Entrega não encontrada.", 404)

        resposta.nota = float(nota)
        db.session.commit()

        return jsonify({"success": True, "message": "Nota registrada com sucesso!"}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao registrar nota.")


# =====================================================
# LISTAR ENTREGAS (PROFESSOR)
# =====================================================
@bp.route("/tarefas/entregas", methods=["GET"])
def listar_entregas():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user or role != "teacher":
            return _json_error("Acesso negado.", 403)

        tarefas_ids = [t.id for t in Tarefa.query.filter_by(
            criado_por=user.id).all()]
        respostas = Resposta.query.filter(Resposta.tarefa_id.in_(tarefas_ids)).order_by(
            Resposta.enviado_em.desc()
        ).all()

        entregas = []
        for r in respostas:
            aluno = User.query.get(r.aluno_id)
            tarefa = Tarefa.query.get(r.tarefa_id)
            entregas.append({
                "id": r.id,
                "aluno_nome": aluno.name if aluno else "Aluno",
                "tarefa_titulo": tarefa.titulo if tarefa else "Atividade",
                "comentario": r.comentario,
                "nota": r.nota,
                "arquivo_url": f"{request.host_url}api/uploads/{r.conteudo}" if r.conteudo else None,
                "data_envio": r.enviado_em.isoformat() if r.enviado_em else None
            })

        return jsonify({"success": True, "entregas": entregas}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao listar entregas.")


# =====================================================
# LISTAR TAREFAS (ALUNO E PROFESSOR)
# =====================================================
@bp.route("/tarefas/listar", methods=["GET"])
def listar_tarefas():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user:
            return _json_error("Usuário não autenticado.", 403)

        tarefas = []
        if role == "teacher":
            tarefas = Tarefa.query.filter_by(criado_por=user.id).order_by(
                Tarefa.created_at.desc()).all()
        elif role == "student":
            turmas_ids = [r.turma_id for r in AlunoTurma.query.filter_by(
                aluno_id=user.id).all()]
            if turmas_ids:
                tarefas = Tarefa.query.filter(Tarefa.turma_id.in_(
                    turmas_ids)).order_by(Tarefa.created_at.desc()).all()

        tarefas_data = []
        for t in tarefas:
            turma = Turma.query.get(t.turma_id)
            resposta = Resposta.query.filter_by(
                tarefa_id=t.id, aluno_id=user.id).first()
            tarefas_data.append({
                "id": t.id,
                "titulo": t.titulo,
                "descricao": t.descricao,
                "prazo": t.data_entrega.isoformat() if t.data_entrega else None,
                "turma_nome": turma.nome if turma else None,
                "arquivo": t.arquivo,
                "link": t.link,
                "entregue": bool(resposta),
                "data_envio": resposta.enviado_em.isoformat() if resposta else None
            })

        return jsonify({"success": True, "tarefas": tarefas_data}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao listar tarefas.")


# =====================================================
# SERVIR UPLOADS
# =====================================================
@bp.route("/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    try:
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception:
        traceback.print_exc()
        return _json_error("Arquivo não encontrado.", 404)

    # =====================================================
# DASHBOARD PROFESSOR - CONTAGEM DE TURMAS E ATIVIDADES
# =====================================================


@bp.route("/dashboard/resumo", methods=["GET"])
def resumo_dashboard_professor():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)

        if not user or role != "teacher":
            return _json_error("Acesso negado.", 403)

        total_turmas = Turma.query.filter_by(professor_id=user.id).count()
        total_tarefas = (
            Tarefa.query.join(Turma)
            .filter(Turma.professor_id == user.id)
            .count()
        )

        return jsonify({
            "success": True,
            "turmas": total_turmas,
            "atividades": total_tarefas
        }), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao carregar resumo do dashboard.")


# =====================================================
# DASHBOARD ALUNO - TURMAS INSCRITAS E ATIVIDADES PENDENTES
# =====================================================
@bp.route("/dashboard/resumo/aluno", methods=["GET"])
def resumo_dashboard_aluno():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)

        if not user or role != "student":
            return _json_error("Acesso negado.", 403)

        # Contar turmas em que o aluno está matriculado
        total_turmas = (
            TurmaAluno.query.filter_by(aluno_id=user.id).count()
        )

        # Contar atividades pendentes (tarefas em turmas onde o aluno está inscrito e sem entrega)
        subquery_turmas = db.session.query(
            TurmaAluno.turma_id).filter_by(aluno_id=user.id)
        total_pendentes = (
            Tarefa.query
            .filter(Tarefa.turma_id.in_(subquery_turmas))
            .filter(~TarefaEntrega.query.filter(
                (TarefaEntrega.tarefa_id == Tarefa.id) &
                (TarefaEntrega.aluno_id == user.id)
            ).exists())
            .count()
        )

        return jsonify({
            "success": True,
            "turmas": total_turmas,
            "pendentes": total_pendentes
        }), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao carregar resumo do dashboard do aluno.")
