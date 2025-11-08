from app import create_app
from models import db, User

app = create_app()

with app.app_context():
    if not User.query.filter_by(email="demo@techforall.com").first():
        prof = User(name="Prof. Demo",
                    email="prof@techforall.com", role="teacher")
        prof.set_password("123456")
        db.session.add(prof)

    if not User.query.filter_by(email="aluno@techforall.com").first():
        aluno = User(name="Aluno Demo",
                     email="aluno@techforall.com", role="student")
        aluno.set_password("123456")
        db.session.add(aluno)

    db.session.commit()
    print("Usuários demo criados com sucesso!")
