from app import create_app, db
from sqlalchemy import inspect, text

app = create_app()


def column_exists(table_name, column_name):
    """Verifica se uma coluna já existe em uma tabela"""
    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def safe_add_column(table_name, column_name, column_type):
    """Adiciona uma coluna sem recriar tabela"""
    if not column_exists(table_name, column_name):
        with app.app_context():
            print(
                f"🆕 Adicionando coluna '{column_name}' na tabela '{table_name}'...")
            db.session.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};"))
            db.session.commit()
    else:
        print(f"✅ Coluna '{column_name}' já existe em '{table_name}'")


def create_or_update_db():
    """Cria as tabelas e aplica atualizações de estrutura"""
    with app.app_context():
        print("🔧 Criando tabelas (se não existirem)...")
        db.create_all()

        # 🧩 Atualizações automáticas
        print("\n🧱 Verificando atualizações de estrutura...\n")

        # Exemplo: nova coluna para comentário do aluno
        safe_add_column("respostas", "comentario", "TEXT")

        # Exemplo: se futuramente quiser adicionar mais colunas
        # safe_add_column("tarefas", "link", "VARCHAR(255)")
        # safe_add_column("tarefas", "arquivo", "VARCHAR(255)")

        print("\n✅ Banco de dados atualizado com sucesso!")


if __name__ == "__main__":
    create_or_update_db()
