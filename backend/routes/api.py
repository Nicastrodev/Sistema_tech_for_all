from flask import Blueprint, request, jsonify
from models import db, User, Turma
from werkzeug.security import check_password_hash
import random
import string
import os
import openai

# =====================================================
# BLUEPRINT PRINCIPAL
# =====================================================
bp = Blueprint("api", __name__, url_prefix="/api")

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

    return jsonify({
        "success": True,
        "role": user.role,
        "user_id": user.id,
        "name": user.name
    }), 200


# =====================================================
# TURMAS - CRUD COMPLETO
# =====================================================
@bp.route("/turmas", methods=["GET"])
def listar_turmas():
    user_id = request.args.get("userId")
    role = request.args.get("role")

    if not user_id or not role:
        return jsonify({"success": False, "message": "Parâmetros inválidos."}), 400

    try:
        if role == "teacher":
            turmas = Turma.query.filter_by(professor_id=user_id).all()
        else:
            turmas = Turma.query.all()  # futuramente: filtrar por aluno

        return jsonify({
            "success": True,
            "turmas": [
                {
                    "id": t.id,
                    "nome": t.nome,
                    "descricao": t.descricao,
                    "codigo_acesso": t.codigo_acesso,
                    "professor_nome": getattr(t.professor, "name", None)
                } for t in turmas
            ]
        }), 200

    except Exception as e:
        print("Erro ao listar turmas:", e)
        return jsonify({"success": False, "message": "Erro interno ao listar turmas."}), 500


@bp.route("/turmas", methods=["POST"])
def criar_turma():
    data = request.get_json() or {}
    nome = data.get("className")
    descricao = data.get("classDesc")
    professor_id = data.get("professorId")

    if not nome or not professor_id:
        return jsonify({"success": False, "message": "Preencha todos os campos obrigatórios."}), 400

    try:
        codigo = "".join(random.choices(
            string.ascii_uppercase + string.digits, k=6))
        nova_turma = Turma(nome=nome, descricao=descricao,
                           codigo_acesso=codigo, professor_id=professor_id)
        db.session.add(nova_turma)
        db.session.commit()

        return jsonify({
            "success": True,
            "codigo_acesso": codigo,
            "message": f"Turma '{nome}' criada com sucesso!"
        }), 201

    except Exception as e:
        db.session.rollback()
        print("Erro ao criar turma:", e)
        return jsonify({"success": False, "message": "Erro ao criar turma."}), 500


# =====================================================
# TURMA DETALHES (para turma.html)
# =====================================================
@bp.route("/turmas/<int:turma_id>", methods=["GET"])
def obter_turma(turma_id):
    turma = Turma.query.get(turma_id)
    if not turma:
        return jsonify({"success": False, "message": "Turma não encontrada."}), 404

    # Cálculo simulado (substitua com query real depois)
    total_alunos = len(turma.alunos) if hasattr(turma, "alunos") else 0
    media_geral = round(sum(
        [a.media or 0 for a in turma.alunos]) / total_alunos, 1) if total_alunos else 0
    freq_media = round(sum([a.frequencia or 0 for a in turma.alunos]
                           ) / total_alunos, 1) if total_alunos else 0

    return jsonify({
        "success": True,
        "turma": {
            "id": turma.id,
            "nome": turma.nome,
            "descricao": turma.descricao,
            "codigo_acesso": turma.codigo_acesso,
            "total_alunos": total_alunos,
            "media_geral": media_geral,
            "frequencia_media": freq_media
        }
    }), 200


# =====================================================
# ALUNOS DE UMA TURMA (para tabela do turma.html)
# =====================================================
@bp.route("/turmas/<int:turma_id>/alunos", methods=["GET"])
def listar_alunos_turma(turma_id):
    turma = Turma.query.get(turma_id)
    if not turma:
        return jsonify({"success": False, "message": "Turma não encontrada."}), 404

    alunos = getattr(turma, "alunos", [])
    lista = [
        {
            "id": a.id,
            "nome": a.name,
            "email": a.email,
            "frequencia": getattr(a, "frequencia", 0),
            "media": getattr(a, "media", 0)
        }
        for a in alunos
    ]

    return jsonify({"success": True, "alunos": lista}), 200


# =====================================================
# RELATÓRIO DE TURMA
# =====================================================
@bp.route("/relatorios/turma/<int:turma_id>", methods=["GET"])
def gerar_relatorio_turma(turma_id):
    turma = Turma.query.get(turma_id)
    if not turma:
        return jsonify({"success": False, "message": "Turma não encontrada."}), 404

    alunos = getattr(turma, "alunos", [])
    total_alunos = len(alunos)
    media_geral = round(sum([a.media or 0 for a in alunos]) /
                        total_alunos, 1) if total_alunos else 0
    freq_media = round(sum([a.frequencia or 0 for a in alunos]
                           ) / total_alunos, 1) if total_alunos else 0

    return jsonify({
        "success": True,
        "nome_turma": turma.nome,
        "alunos": total_alunos,
        "atividades": random.randint(3, 10),  # Exemplo: número de atividades
        "media_geral": media_geral,
        "frequencia_media": freq_media
    }), 200


# =====================================================
# CHAT IA (com suporte a OpenAI)
# =====================================================
@bp.route("/chat", methods=["POST"])
def chat_ai():
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    user_name = data.get("user_name", "Usuário")
    first_message = data.get("first_message", False)

    if first_message:
        return jsonify({
            "response": f"Olá, {user_name}! 👋 Sou sua assistente virtual da **Tech For All**. "
            f"Posso te ajudar com dúvidas sobre aulas, atividades e tecnologia. "
            f"O que você gostaria de saber hoje?"
        })

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({
            "response": f"(Modo simulado) Você disse: '{message}'. "
            "Quando configurar sua chave de API OpenAI, responderei com inteligência real. 🤖"
        })

    try:
        client = openai.OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Você é uma assistente educacional da plataforma Tech For All. "
                    "Responda de forma amigável, objetiva e clara, incentivando o aprendizado. "
                    "Evite respostas muito longas e use linguagem acessível."
                )},
                {"role": "user", "content": message}
            ]
        )

        response = completion.choices[0].message.content.strip()
        return jsonify({"response": response})

    except Exception as e:
        print("Erro no chat IA:", e)
        return jsonify({
            "response": "⚠️ Ocorreu um erro ao conectar com a IA. Tente novamente mais tarde."
        }), 500
