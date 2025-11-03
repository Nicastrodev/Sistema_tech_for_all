from app import create_app
from models import db, User
from werkzeug.security import check_password_hash

app = create_app()
with app.app_context():
    u = User.query.filter_by(email="demo@techforall.com").first()
    print("Usuário:", u.name)
    print("Hash salvo:", u.password_hash)
    print("Senha confere?", check_password_hash(u.password_hash, "123456"))