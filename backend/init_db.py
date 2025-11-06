from app import create_app
from models import db


def inicializar_banco():
    """Cria todas as tabelas do banco configurado no app Flask."""
    try:
        app = create_app()
        with app.app_context():
            db.create_all()
            print("✅ Banco de dados inicializado com sucesso!")
    except Exception as e:
        print("❌ Erro ao criar o banco de dados:")
        print(e)


if __name__ == "__main__":
    print("🔧 Iniciando criação do banco de dados...")
    inicializar_banco()
