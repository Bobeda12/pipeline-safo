# preparar_db_completo.py
import sqlite3
import os

NOME_BANCO = os.getenv("DB_NAME", "projeto_grande.db")

def preparar_banco():
    print(f"Preparando o banco de dados '{NOME_BANCO}'...")
    conn = sqlite3.connect(NOME_BANCO)
    cursor = conn.cursor()

    # Cria a tabela de usuários se não existir
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL 
    );
    """)
    print("Tabela 'users' verificada/criada.")

    # Insere um usuário de teste se ele não existir
    try:
        cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", ('admin@ime.br', 'admin'))
        print("Usuário de teste 'admin@ime.br' com senha 'admin' criado.")
    except sqlite3.IntegrityError:
        print("Usuário de teste 'admin@ime.br' já existe.")

    conn.commit()
    conn.close()
    print("Preparação do banco de dados concluída.")

if __name__ == '__main__':
    # Rode este script uma vez para garantir que a tabela de usuários exista
    preparar_banco()