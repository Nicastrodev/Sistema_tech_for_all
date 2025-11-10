# routes/api.py
from flask import request, jsonify
import requests
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors

from flask import Blueprint, request, jsonify, send_from_directory, current_app
from models import db, User, Turma, AlunoTurma, Tarefa, Resposta
from datetime import datetime
import os
import random
import string
import traceback
import subprocess
import json
import shlex

bp = Blueprint("api", __name__, url_prefix="/api")

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Caminho para o executável C (calculos.exe) - ajuste se necessário
CALCULOS_EXE_PATH = os.path.join(os.getcwd(), "calculos.exe")


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
    """
    Extrai X-User-Id / X-User-Role de headers, query ou body JSON.
    Normaliza role para lowercase quando presente.
    """
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
    """Salva o arquivo e retorna o nome gerado (ou None)."""
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
# UTIL: executar calculos.exe (fallback para Python)
# =====================================================

def run_c_calculos(notas_list, exame_final=-1.0):
    """
    Tenta executar o calculos.exe com os argumentos:
       <notas_como_csv> <exame_final>
    Exemplo de retorno esperado (string stdout):
       {"media": 7.50, "situacao": "Aprovado"}
    Se o exe não existir ou falhar, faz o cálculo em Python (fallback).
    """
    # prepara string de notas separadas por vírgula
    try:
        notas_csv = ",".join([str(float(n))
                             for n in notas_list]) if notas_list else ""
    except Exception:
        notas_csv = ""

    # se exe existir, tenta executar
    if os.path.exists(CALCULOS_EXE_PATH) and os.path.isfile(CALCULOS_EXE_PATH):
        try:
            args = [CALCULOS_EXE_PATH, notas_csv or "",
                    str(float(exame_final))]
            completed = subprocess.run(
                args, capture_output=True, text=True, timeout=10)
            stdout = completed.stdout.strip()
            stderr = completed.stderr.strip()
            if completed.returncode == 0 and stdout:
                try:
                    result = json.loads(stdout)
                    return {
                        "media": float(result.get("media", 0.0)),
                        "situacao": result.get("situacao", "")
                    }
                except Exception:
                    try:
                        media_val = float(stdout.strip())
                        situacao = ""
                        if media_val >= 7.0:
                            situacao = "Aprovado"
                        elif media_val >= 5.0:
                            situacao = "Recuperação"
                        else:
                            situacao = "Reprovado"
                        return {"media": media_val, "situacao": situacao}
                    except Exception:
                        pass
            else:
                current_app.logger.debug("calculos.exe stderr: %s", stderr)
        except Exception as e:
            current_app.logger.debug(
                "Erro executando calculos.exe: %s", str(e))

    # --- fallback: calcular em Python (mesma lógica do C) ---
    try:
        notas = [float(n) for n in notas_list if n is not None]
    except Exception:
        notas = []

    media_atividades = 0.0
    if notas:
        media_atividades = sum(notas) / len(notas)

    media_final = media_atividades
    if exame_final is not None and exame_final >= 0:
        try:
            ex = float(exame_final)
            media_final = (media_atividades + ex) / 2.0
        except Exception:
            pass

    situacao = "Reprovado"
    if media_final >= 7.0:
        situacao = "Aprovado"
    elif media_final >= 5.0:
        situacao = "Recuperação"

    return {"media": round(media_final, 2), "situacao": situacao}


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
# TURMAS - CRIAR / LISTAR / OBTER / ATUALIZAR / EXCLUIR
# =====================================================
@bp.route("/turmas", methods=["POST"])
def criar_turma():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user or role != "teacher":
            return _json_error("Apenas professores podem criar turmas.", 403)

        data = request.form if request.form else (request.get_json() or {})
        nome = (data.get("nome") or "").strip()
        descricao = data.get("descricao")
        if not nome:
            return _json_error("O nome da turma é obrigatório.", 400)

        codigo_acesso = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=6))
        turma = Turma(nome=nome, descricao=descricao,
                      codigo_acesso=codigo_acesso, professor_id=user.id)

        db.session.add(turma)
        db.session.commit()

        return jsonify({"success": True, "turma_id": turma.id, "codigo_acesso": codigo_acesso}), 201
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao criar turma.")


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


@bp.route("/turmas/<int:turma_id>", methods=["GET"])
def obter_turma(turma_id):
    try:
        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)

        # alunos da turma
        alunos_rel = AlunoTurma.query.filter_by(turma_id=turma.id).all()
        total_alunos = len(alunos_rel)

        # média geral das notas dessa turma (usando apenas respostas com nota)
        respostas = (
            Resposta.query.join(Tarefa, Tarefa.id == Resposta.tarefa_id)
            .filter(Tarefa.turma_id == turma.id, Resposta.nota != None)
            .all()
        )
        notas = [r.nota for r in respostas if r.nota is not None]
        media_geral = round(sum(notas) / len(notas), 1) if notas else 0.0

        # contar atividades da turma
        total_tarefas = Tarefa.query.filter_by(turma_id=turma.id).count()

        # calcular frequencia média da turma:
        # para cada aluno, frequencia = entregues / total_tarefas; média das frequências
        frequencias = []
        for rel in alunos_rel:
            aluno_id = rel.aluno_id
            if total_tarefas == 0:
                frequencias.append(0.0)
                continue
            entregues = Resposta.query.join(Tarefa, Tarefa.id == Resposta.tarefa_id) \
                .filter(Tarefa.turma_id == turma.id, Resposta.aluno_id == aluno_id, Resposta.enviado_em.isnot(None)).count()
            freq = (entregues / total_tarefas) * 100.0
            frequencias.append(freq)
        frequencia_media = round(
            sum(frequencias) / len(frequencias), 1) if frequencias else 0.0

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
                "total_tarefas": total_tarefas,
                "frequencia_media": frequencia_media
            },
            "alunos": alunos_data
        }), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao carregar detalhes da turma.")


@bp.route("/turmas/<int:turma_id>", methods=["PUT"])
def atualizar_turma(turma_id):
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)

        if not user or role != "teacher":
            return _json_error("Apenas professores podem editar turmas.", 403)

        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)

        if turma.professor_id != user.id:
            return _json_error("Você não tem permissão para editar esta turma.", 403)

        data = request.get_json() or {}
        nome = (data.get("nome") or "").strip()
        descricao = data.get("descricao")

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
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao atualizar turma.")


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

        if turma.professor_id != user.id:
            return _json_error("Você não tem permissão para excluir esta turma.", 403)

        # remover relações e tarefas/respostas associadas
        AlunoTurma.query.filter_by(turma_id=turma.id).delete()
        tarefas = Tarefa.query.filter_by(turma_id=turma.id).all()
        for tarefa in tarefas:
            Resposta.query.filter_by(tarefa_id=tarefa.id).delete()
            db.session.delete(tarefa)

        db.session.delete(turma)
        db.session.commit()
        return jsonify({"success": True, "message": "Turma excluída com sucesso!"}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao excluir turma.")


# =====================================================
# ADICIONAR / REMOVER ALUNO (rotas usadas pelo front)
# =====================================================
@bp.route("/turmas/<int:turma_id>/adicionar_aluno", methods=["POST"])
def adicionar_aluno_turma(turma_id):
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user or role != "teacher":
            return _json_error("Apenas professores podem adicionar alunos.", 403)

        data = request.get_json() or {}
        aluno_id = data.get("alunoId")
        if not aluno_id:
            return _json_error("alunoId é obrigatório.", 400)

        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)
        if turma.professor_id != user.id:
            return _json_error("Você não tem permissão para adicionar alunos nesta turma.", 403)

        aluno = User.query.get(aluno_id)
        if not aluno:
            return _json_error("Aluno não encontrado.", 404)

        if AlunoTurma.query.filter_by(aluno_id=aluno.id, turma_id=turma.id).first():
            return jsonify({"success": False, "message": "Aluno já está na turma."}), 400

        rel = AlunoTurma(aluno_id=aluno.id, turma_id=turma.id)
        db.session.add(rel)
        db.session.commit()
        return jsonify({"success": True, "message": "Aluno adicionado com sucesso."}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao adicionar aluno.")

# =====================================================
# ENTRAR EM TURMA (ALUNO)
# =====================================================


@bp.route("/turmas/entrar", methods=["POST"])
def entrar_turma():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)

        if not user or role != "student":
            return _json_error("Apenas alunos podem entrar em turmas.", 403)

        data = request.get_json() or {}
        codigo = (data.get("codigo") or data.get(
            "codigo_acesso") or "").strip().upper()

        if not codigo:
            return _json_error("Código da turma é obrigatório.", 400)

        turma = Turma.query.filter_by(codigo_acesso=codigo).first()
        if not turma:
            return _json_error("Código de turma inválido.", 404)

        # verificar se aluno já está na turma
        relacao_existente = AlunoTurma.query.filter_by(
            aluno_id=user.id, turma_id=turma.id).first()
        if relacao_existente:
            return jsonify({
                "success": False,
                "message": "Você já está matriculado nesta turma."
            }), 400

        nova_relacao = AlunoTurma(aluno_id=user.id, turma_id=turma.id)
        db.session.add(nova_relacao)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Você entrou na turma '{turma.nome}' com sucesso!",
            "turma": {
                "id": turma.id,
                "nome": turma.nome,
                "descricao": turma.descricao,
                "professor_nome": getattr(turma.professor, "name", None)
            }
        }), 200

    except Exception as e:
        traceback.print_exc()
        return _json_error(f"Erro ao entrar na turma: {str(e)}")


@bp.route("/turmas/<int:turma_id>/aluno/<int:aluno_id>", methods=["DELETE"])
def remover_aluno_turma(turma_id, aluno_id):
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user or role != "teacher":
            return _json_error("Apenas professores podem remover alunos.", 403)

        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)
        if turma.professor_id != user.id:
            return _json_error("Você não tem permissão para remover alunos nesta turma.", 403)

        rel = AlunoTurma.query.filter_by(
            aluno_id=aluno_id, turma_id=turma_id).first()
        if not rel:
            return _json_error("Relação aluno-turma não encontrada.", 404)

        db.session.delete(rel)
        db.session.commit()
        return jsonify({"success": True, "message": "Aluno removido da turma."}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao remover aluno da turma.")


# =====================================================
# LISTAR ALUNOS (rota separada usada pelo front)
# =====================================================
@bp.route("/turmas/<int:turma_id>/alunos", methods=["GET"])
def listar_alunos_turma(turma_id):
    """
    Rota que retorna lista de alunos com:
      - id, nome, email
      - media calculada (usando calculos.exe se disponível)
      - frequencia calculada = (tarefas_entregues / total_tarefas) * 100
    """
    try:
        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)

        relacoes = AlunoTurma.query.filter_by(turma_id=turma_id).all()
        alunos_data = []

        total_tarefas = Tarefa.query.filter_by(turma_id=turma_id).count()

        for rel in relacoes:
            aluno = User.query.get(rel.aluno_id)
            if not aluno:
                continue

            # pegar todas as respostas do aluno nesta turma (mesmo sem nota)
            respostas = (
                Resposta.query.join(Tarefa, Tarefa.id == Resposta.tarefa_id)
                .filter(Tarefa.turma_id == turma_id, Resposta.aluno_id == aluno.id)
                .all()
            )

            # notas válidas para cálculo de média (quando houver nota atribuída)
            notas_validas = [r.nota for r in respostas if r.nota is not None]

            # Se quiser passar exame_final, ajustar para obter esse dado (aqui consideramos -1)
            exame_final = -1

            # usar bloco C para calcular média/situação (com fallback)
            calc_result = run_c_calculos(notas_validas, exame_final)

            # frequência baseada em entregas
            entregues = len([r for r in respostas if r.enviado_em is not None])

            frequencia = 0.0
            if total_tarefas > 0:
                frequencia = (entregues / total_tarefas) * 100.0
            # formatar para 1 casa
            frequencia_fmt = round(frequencia, 1)

            alunos_data.append({
                "id": aluno.id,
                "nome": aluno.name,
                "email": aluno.email,
                "media": calc_result.get("media", 0.0),
                "situacao": calc_result.get("situacao", ""),
                "frequencia": frequencia_fmt
            })

        return jsonify({"success": True, "alunos": alunos_data}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao listar alunos da turma.")


# =====================================================
# TAREFAS / ATIVIDADES (CRIAR / LISTAR / ALIAS)
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


# rota alternativa sem /listar (alguns fronts chamam /tarefas)
@bp.route("/tarefas", methods=["GET"])
def listar_tarefas_alias():
    return listar_tarefas()


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

        arquivo = request.files.get("arquivo") or request.files.get("file")
        comentario = (request.form.get("comentario")
                      or request.form.get("conteudo") or "").strip()

        if not arquivo and not comentario:
            return _json_error("Envie um arquivo ou comentário.", 400)

        filename = save_uploaded_file(arquivo) if arquivo else None

        resposta = Resposta.query.filter_by(
            tarefa_id=tarefa.id, aluno_id=user.id).first()
        if not resposta:
            resposta = Resposta(tarefa_id=tarefa.id, aluno_id=user.id)

        # Preferir salvar arquivo no campo conteudo para manter compatibilidade com front antigo
        resposta.conteudo = filename or (comentario if comentario else "")
        resposta.comentario = comentario
        resposta.enviado_em = datetime.utcnow()

        db.session.add(resposta)
        db.session.commit()

        return jsonify({"success": True, "message": "Atividade enviada com sucesso!", "resposta_id": resposta.id}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao enviar atividade.")


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
        if not tarefas_ids:
            return jsonify({"success": True, "entregas": []}), 200

        respostas = Resposta.query.filter(Resposta.tarefa_id.in_(
            tarefas_ids)).order_by(Resposta.enviado_em.desc()).limit(200).all()

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
# AVALIAR ENTREGA (PROFESSOR)
# =====================================================
@bp.route("/tarefas/<int:resposta_id>/avaliar", methods=["POST"])
def avaliar_entrega(resposta_id):
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user or role != "teacher":
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
# SERVIR UPLOADS
# =====================================================
@bp.route("/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    try:
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception:
        traceback.print_exc()
        return _json_error("Arquivo não encontrado.", 404)


@bp.route("/uploads/reports/<path:filename>", methods=["GET"])
def serve_report(filename):
    try:
        reports_folder = os.path.join(UPLOAD_FOLDER, "reports")
        return send_from_directory(reports_folder, filename)
    except Exception:
        traceback.print_exc()
        return _json_error("Relatório não encontrado.", 404)


# =====================================================
# DASHBOARD: RESUMOS E CONTADORES
# =====================================================
@bp.route("/dashboard/resumo", methods=["GET"])
def resumo_dashboard_professor():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user or role != "teacher":
            return _json_error("Acesso negado.", 403)

        total_turmas = Turma.query.filter_by(professor_id=user.id).count()
        total_tarefas = Tarefa.query.join(Turma).filter(
            Turma.professor_id == user.id).count()

        return jsonify({"success": True, "turmas": total_turmas, "atividades": total_tarefas}), 200
    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao carregar resumo do dashboard.")


@bp.route("/dashboard/resumo/aluno", methods=["GET"])
def resumo_dashboard_aluno():
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)
        if not user or role != "student":
            return _json_error("Acesso negado.", 403)

        turma_ids = [r.turma_id for r in AlunoTurma.query.filter_by(
            aluno_id=user.id).all()]
        if not turma_ids:
            return jsonify({"success": True, "turmas": 0, "pendentes": 0, "frequencia": 0}), 200

        # Total de tarefas nas turmas do aluno
        total_tarefas = Tarefa.query.filter(
            Tarefa.turma_id.in_(turma_ids)
        ).count()

        # Total de tarefas entregues pelo aluno
        total_entregues = (
            Resposta.query.filter(Resposta.aluno_id == user.id)
            .join(Tarefa, Tarefa.id == Resposta.tarefa_id)
            .filter(Tarefa.turma_id.in_(turma_ids))
            .count()
        )

        pendentes = max(total_tarefas - total_entregues, 0)

        # 🔢 Calcula frequência percentual com base nas entregas
        frequencia = 0.0
        if total_tarefas > 0:
            frequencia = (total_entregues / total_tarefas) * 100.0

        return jsonify({
            "success": True,
            "turmas": len(turma_ids),
            "pendentes": pendentes,
            "frequencia": round(frequencia, 1)
        }), 200

    except Exception:
        traceback.print_exc()
        return _json_error("Erro ao carregar resumo do dashboard do aluno.")

# =====================================================
# RELATÓRIOS - GERAÇÃO DE PDF
# =====================================================


@bp.route("/relatorios/turma/<int:turma_id>/pdf", methods=["GET"])
def gerar_relatorio_turma_pdf(turma_id):
    try:
        user_id, role = _extract_userid_and_role_from_request()
        user = _get_user_by_id(user_id)

        if not user or role != "teacher":
            return _json_error("Apenas professores podem gerar relatórios.", 403)

        turma = Turma.query.get(turma_id)
        if not turma:
            return _json_error("Turma não encontrada.", 404)

        alunos_rel = AlunoTurma.query.filter_by(turma_id=turma.id).all()
        total_tarefas = Tarefa.query.filter_by(turma_id=turma.id).count()

        dados_alunos = []
        for rel in alunos_rel:
            aluno = User.query.get(rel.aluno_id)
            if not aluno:
                continue

            # Buscar respostas e notas do aluno nesta turma
            respostas = (
                Resposta.query.join(Tarefa, Tarefa.id == Resposta.tarefa_id)
                .filter(
                    Tarefa.turma_id == turma.id,
                    Resposta.aluno_id == aluno.id
                )
                .all()
            )

            notas = [r.nota for r in respostas if r.nota is not None]
            calc_result = run_c_calculos(notas, -1)
            media_str = f"{calc_result.get('media', 0.0):.1f}"

            # Calcular frequência baseada em entregas
            entregues = len([r for r in respostas if r.enviado_em is not None])
            frequencia = 0.0
            if total_tarefas > 0:
                frequencia = (entregues / total_tarefas) * 100.0
            freq_str = f"{frequencia:.1f}%"

            dados_alunos.append([aluno.name, aluno.email, media_str, freq_str])

        if not dados_alunos:
            dados_alunos = [["Nenhum aluno cadastrado", "-", "-", "-"]]

        # Caminho para salvar PDF
        reports_folder = os.path.join(UPLOAD_FOLDER, "reports")
        os.makedirs(reports_folder, exist_ok=True)
        filename = f"relatorio_turma_{turma.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        filepath = os.path.join(reports_folder, filename)

        # Criação do PDF
        doc = SimpleDocTemplate(filepath, pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        elements = []

        title = Paragraph(
            f"<strong>Relatório da Turma:</strong> {turma.nome}", styles["Title"]
        )
        subtitle = Paragraph(
            f"Professor: {user.name} &nbsp;&nbsp;|&nbsp;&nbsp; Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            styles["Normal"]
        )

        elements.append(title)
        elements.append(Spacer(1, 12))
        elements.append(subtitle)
        elements.append(Spacer(1, 20))

        # Cabeçalhos e tabela atualizada com 4 colunas
        data = [["Aluno", "Email", "Média", "Frequência"]] + dados_alunos

        table = Table(data, colWidths=[7 * cm, 8 * cm, 3 * cm, 3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )

        elements.append(table)
        doc.build(elements)

        pdf_url = f"{request.host_url}api/uploads/reports/{filename}"
        return jsonify({"success": True, "url": pdf_url}), 200

    except Exception as e:
        traceback.print_exc()
        return _json_error("Erro ao gerar relatório em PDF.")


 # ========================================
# 🤖 ROTA DE CHAT IA - ASSISTENTE TECH FOR ALL
# ========================================
chat_memory = {}  # memória leve por sessão (em RAM)


@bp.route("/ia/chat", methods=["POST"])
def ia_chat():
    import google.generativeai as genai
    import os

    try:
        data = request.get_json()
        question = data.get("question", "").strip()
        user = data.get("user", {})
        student_id = user.get("id", "anon")
        student_name = user.get("name", "Aluno")

        if not question:
            return jsonify({"success": False, "message": "Mensagem vazia."}), 400

        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            print("❌ ERRO: GEMINI_API_KEY não configurada.")
            return jsonify({"success": False, "message": "Chave da Gemini não configurada."}), 500

        genai.configure(api_key=GEMINI_API_KEY)

        # Memória por aluno (últimas 5 mensagens)
        global chat_memory
        history = chat_memory.get(student_id, [])
        history.append({"role": "user", "content": question})
        history = history[-5:]

        # Instrução principal
        system_prompt = f"""
Você é o **Assistente Tech For All**, mentor digital dos alunos da plataforma Tech For All.

🎯 Sua missão:
Ajudar o aluno {student_name} a aprender com autonomia — nunca entregue respostas diretas logo de início.
Explique passo a passo, incentive o raciocínio e aja como um tutor paciente e didático.

📘 Quando o aluno perguntar sobre o sistema:
- "Como entrar em uma turma" → Explique que ele deve pedir o código ao professor e inserir no painel.
- "Como ver atividades" → Indique o menu “Atividades”.
- "Como ver notas ou frequência" → Informe que estão dentro da turma.
- "O que é a Tech For All" → Diga que é uma plataforma de inclusão digital com IA educativa.

💬 Estilo:
- Sempre responda em português.
- Seja gentil e claro.
- Nunca repita mensagens genéricas.
- Termine respostas com algo motivador, como “Quer tentar comigo?” ou “Quer que eu te guie passo a passo?”.
"""

        # Modelo Gemini atualizado
        model = genai.GenerativeModel("gemini-2.0-flash")

        # Construção da conversa no formato correto
        messages = [
            {"role": "user", "parts": [system_prompt]},
            *[{"role": "user", "parts": [m["content"]]} for m in history],
        ]

        response = model.generate_content(messages)
        answer = (
            response.text.strip()
            if hasattr(response, "text") and response.text
            else "Desculpe, não consegui entender. Pode tentar reformular?"
        )

        # Atualiza histórico
        history.append({"role": "model", "content": answer})
        chat_memory[student_id] = history[-5:]

        return jsonify({"success": True, "answer": answer})

    except Exception as e:
        print("❌ Erro no chat Gemini:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500
