from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'teacher' or 'student'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relações:
    turmas_professor = db.relationship(
        "Turma", back_populates="professor", lazy="dynamic")
    turmas_aluno = db.relationship(
        "AlunoTurma", back_populates="aluno", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password, method="pbkdf2:sha256")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Material(db.Model):
    __tablename__ = "material"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text)
    arquivo = db.Column(db.String(255))
    data_publicacao = db.Column(db.DateTime, default=datetime.utcnow)
    professor_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # relacionamento opcional — permite acessar material.professor
    professor = db.relationship(
        "User", backref=db.backref("materiais", lazy="dynamic"))

    def to_dict(self, host_url=""):
        return {
            "id": self.id,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "arquivo": self.arquivo,
            "url": f"{host_url}api/uploads/{self.arquivo}" if self.arquivo else None,
            "data_publicacao": self.data_publicacao.isoformat()
        }


class Turma(db.Model):
    __tablename__ = "turmas"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    codigo_acesso = db.Column(db.String(12), unique=True, nullable=False)
    professor_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False)
    num_alunos = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relações:
    professor = db.relationship("User", back_populates="turmas_professor")
    alunos_assoc = db.relationship(
        "AlunoTurma", back_populates="turma", lazy="dynamic")
    tarefas = db.relationship("Tarefa", back_populates="turma", lazy="dynamic")


class AlunoTurma(db.Model):
    """
    Tabela de associação entre alunos (User.role == 'student') e turmas.
    Guarda também frequência e média por aluno na turma.
    """
    __tablename__ = "alunos_turmas"

    id = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    turma_id = db.Column(db.Integer, db.ForeignKey(
        "turmas.id"), nullable=False)
    frequencia = db.Column(db.Float, default=0.0)
    media = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    aluno = db.relationship("User", back_populates="turmas_aluno")
    turma = db.relationship("Turma", back_populates="alunos_assoc")


class Tarefa(db.Model):
    __tablename__ = "tarefas"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    data_entrega = db.Column(db.Date, nullable=True)
    turma_id = db.Column(db.Integer, db.ForeignKey(
        "turmas.id"), nullable=False)
    criado_por = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    turma = db.relationship("Turma", back_populates="tarefas")
    respostas = db.relationship(
        "Resposta", back_populates="tarefa", lazy="dynamic")


class Resposta(db.Model):
    __tablename__ = "respostas"

    id = db.Column(db.Integer, primary_key=True)
    tarefa_id = db.Column(db.Integer, db.ForeignKey(
        "tarefas.id"), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    conteudo = db.Column(db.Text, nullable=True)
    enviado_em = db.Column(db.DateTime, default=datetime.utcnow)
    nota = db.Column(db.Float, nullable=True)  # nota atribuída pelo professor

    tarefa = db.relationship("Tarefa", back_populates="respostas")
    aluno = db.relationship("User", lazy="joined")
