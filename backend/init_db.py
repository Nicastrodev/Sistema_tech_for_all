from app import create_app
# MODIFICADO: Importar todos os modelos necessários
from models import db, User, Material, Turma, AlunoTurma, Tarefa, Resposta


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
