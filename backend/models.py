from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


# =====================================================
# USER
# =====================================================
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'teacher' or 'student'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relações
    turmas_professor = db.relationship(
        "Turma",
        back_populates="professor",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    turmas_aluno = db.relationship(
        "AlunoTurma",
        back_populates="aluno",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    materiais = db.relationship(
        "Material",
        back_populates="professor",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    # Métodos auxiliares
    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password, method="pbkdf2:sha256")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.id} ({self.role}) - {self.name}>"


# =====================================================
# MATERIAL
# =====================================================
class Material(db.Model):
    __tablename__ = "materiais"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text)
    arquivo = db.Column(db.String(255))
    data_publicacao = db.Column(db.DateTime, default=datetime.utcnow)
    professor_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False)

    professor = db.relationship("User", back_populates="materiais")

    def to_dict(self, host_url=""):
        return {
            "id": self.id,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "arquivo": self.arquivo,
            "url": f"{host_url}api/uploads/{self.arquivo}" if self.arquivo else None,
            "data_publicacao": self.data_publicacao.isoformat()
        }

    def __repr__(self):
        return f"<Material {self.id} - {self.titulo}>"


# =====================================================
# TURMA
# =====================================================
class Turma(db.Model):
    __tablename__ = "turmas"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.Text)
    codigo_acesso = db.Column(db.String(12), unique=True, nullable=False)
    professor_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False)
    num_alunos = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    professor = db.relationship("User", back_populates="turmas_professor")
    alunos_assoc = db.relationship(
        "AlunoTurma",
        back_populates="turma",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    tarefas = db.relationship(
        "Tarefa",
        back_populates="turma",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Turma {self.id} - {self.nome}>"


# =====================================================
# ALUNO TURMA (associação)
# =====================================================
class AlunoTurma(db.Model):
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

    def __repr__(self):
        return f"<AlunoTurma aluno={self.aluno_id} turma={self.turma_id}>"


# =====================================================
# TAREFA
# =====================================================
class Tarefa(db.Model):
    __tablename__ = "tarefas"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text)
    data_entrega = db.Column(db.Date)
    turma_id = db.Column(db.Integer, db.ForeignKey(
        "turmas.id"), nullable=False)
    criado_por = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    turma = db.relationship("Turma", back_populates="tarefas")
    respostas = db.relationship(
        "Resposta",
        back_populates="tarefa",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Tarefa {self.id} - {self.titulo}>"


# =====================================================
# RESPOSTA (entrega de aluno)
# =====================================================
class Resposta(db.Model):
    __tablename__ = "respostas"

    id = db.Column(db.Integer, primary_key=True)
    tarefa_id = db.Column(db.Integer, db.ForeignKey(
        "tarefas.id"), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    conteudo = db.Column(db.Text)
    enviado_em = db.Column(db.DateTime, default=datetime.utcnow)
    nota = db.Column(db.Float)

    tarefa = db.relationship("Tarefa", back_populates="respostas")
    aluno = db.relationship("User", lazy="joined")

    def __repr__(self):
        return f"<Resposta {self.id} - tarefa={self.tarefa_id} aluno={self.aluno_id}>"
