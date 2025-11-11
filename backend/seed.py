from app import create_app
from models import db, User

app = create_app()

with app.app_context():
    # ✅ Garante que as tabelas existam antes de inserir usuários
    print("🚀 Criando tabelas (se não existirem)...")
    db.create_all()

    # Cria usuários de demonstração se ainda não existirem
    if not User.query.filter_by(email="prof@techforall.com").first():
        prof = User(name="Prof. Demo",
                    email="prof@techforall.com", role="teacher")
        prof.set_password("123456")
        db.session.add(prof)
        print("👨‍🏫 Professor demo criado: prof@techforall.com / 123456")

    if not User.query.filter_by(email="aluno@techforall.com").first():
        aluno = User(name="Aluno Demo",
                     email="aluno@techforall.com", role="student")
        aluno.set_password("123456")
        db.session.add(aluno)
        print("🎓 Aluno demo criado: aluno@techforall.com / 123456")

    db.session.commit()
    print("✅ Usuários demo criados/verificados com sucesso!")
