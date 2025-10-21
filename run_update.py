import sqlite3
import random
import time
from faker import Faker
import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# --- CONFIGURAÇÕES UNIFICADAS ---
NOME_BANCO = os.getenv("DB_NAME", "projeto_grande.db")
NUM_EDITAIS = 500
NUM_LINHAS_PESQUISA = 200
NUM_USUARIOS = 10

fake = Faker('pt_BR')

# --- BASE DE CONHECIMENTO ---
AREAS_CONHECIMENTO = [
    {
        "area": "Inteligência Artificial", "programa": "PPGIA", "substantivos": ["algoritmos", "redes neurais", "aprendizado de máquina"], "verbos": ["otimizar", "desenvolver", "implementar"], "adjetivos": ["inteligente", "preditivo", "autônomo"]
    },
    {
        "area": "Computação Quântica", "programa": "PPGCQ", "substantivos": ["qubits", "algoritmos quânticos", "criptografia pós-quântica"], "verbos": ["projetar", "simular", "construir"], "adjetivos": ["quântico", "seguro", "robusto"]
    },
    {
        "area": "Energias Renováveis", "programa": "PPGER", "substantivos": ["energia solar", "energia eólica", "biomassa"], "verbos": ["gerar", "armazenar", "distribuir"], "adjetivos": ["sustentável", "limpa", "renovável"]
    }
]
FRASES_ELEGIBILIDADE = [
    "Este edital é aberto a toda instituição de ciência e tecnologia (ICT) do país.",
    "Universidades públicas e institutos de pesquisa são o público-alvo principal.",
    "Esta chamada é de uso exclusivo para empresas de base tecnológica e startups."
]

def gerar_linha_pesquisa(base):
    linha = f"Estudo de {random.choice(base['substantivos'])}"
    descricao = f"Análise e desenvolvimento de sistemas para {base['area']}, com foco em {random.choice(base['substantivos'])}."
    return linha, descricao

def gerar_edital(base):
    titulo = f"Chamada Pública nº {random.randint(1, 99)}/2025 - Fomento em {base['area']}"
    texto_base = f"O presente edital visa selecionar propostas para apoio financeiro a projetos em {base['area']}. "
    frase_elegibilidade = random.choice(FRASES_ELEGIBILIDADE)
    return titulo, texto_base + frase_elegibilidade

def run_complete_update():
    """
    Executa todo o pipeline: cria o DB, popula, calcula embeddings e encontra matches.
    """
    print("--- INICIANDO TAREFA DE ATUALIZAÇÃO COMPLETA ---")
    start_time = time.time()

    # ETAPA 1: Criar DB e tabelas
    if os.path.exists(NOME_BANCO):
        os.remove(NOME_BANCO)
    conn = sqlite3.connect(NOME_BANCO)
    cursor = conn.cursor()

    print("[ETAPA 1] Criando tabelas...")
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);")
    cursor.execute("CREATE TABLE edital (id INTEGER PRIMARY KEY, titulo TEXT, orgao TEXT, link_pagina TEXT, texto_pdf TEXT, status TEXT);")
    cursor.execute("""
        CREATE TABLE linha_ime (
            id INTEGER PRIMARY KEY AUTOINCREMENT, programa TEXT, linha TEXT, descricao TEXT, 
            emails_contato TEXT, embedding BLOB, user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    cursor.execute("""
        CREATE TABLE match (
            edital_id INTEGER, edital_titulo TEXT, linha_id INTEGER, 
            linha_nome TEXT, programa TEXT, score REAL
        );
    """)
    print("Tabelas criadas com sucesso.")

    # ETAPA 2: Popular com dados de teste
    print("[ETAPA 2] Gerando e inserindo dados...")
    users = [('admin@ime.br', 'admin')] + [(f'user{i}@ime.br', '123') for i in range(2, NUM_USUARIOS + 1)]
    cursor.executemany("INSERT INTO users (email, password) VALUES (?, ?);", users)

    linhas_data = []
    for _ in range(NUM_LINHAS_PESQUISA):
        base = random.choice(AREAS_CONHECIMENTO)
        linha, desc = gerar_linha_pesquisa(base)
        user_id = random.randint(1, NUM_USUARIOS)
        linhas_data.append((base['programa'], linha, desc, fake.email(), user_id))
    cursor.executemany("INSERT INTO linha_ime (programa, linha, descricao, emails_contato, user_id) VALUES (?, ?, ?, ?, ?);", linhas_data)

    editais_data = []
    for i in range(1, NUM_EDITAIS + 1):
        base = random.choice(AREAS_CONHECIMENTO)
        titulo, texto_pdf = gerar_edital(base)
        editais_data.append((i, titulo, "FINEP", fake.url(), texto_pdf, "aberto"))
    cursor.executemany("INSERT INTO edital VALUES (?, ?, ?, ?, ?, ?);", editais_data)
    
    conn.commit()
    conn.close()
    print("Dados inseridos com sucesso.")

    # ETAPA 3: Calcular e salvar embeddings
    print("[ETAPA 3] Pré-calculando embeddings...")
    engine = create_engine(f'sqlite:///{NOME_BANCO}')
    df_linhas = pd.read_sql_table('linha_ime', engine)
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    embeddings = model.encode(df_linhas['descricao'].tolist(), show_progress_bar=True)
    
    conn = sqlite3.connect(NOME_BANCO)
    cursor = conn.cursor()
    for index, embedding in enumerate(embeddings):
        linha_id = int(df_linhas.iloc[index]['id'])
        cursor.execute("UPDATE linha_ime SET embedding = ? WHERE id = ?", (embedding.astype(np.float32).tobytes(), linha_id))
    conn.commit()
    conn.close()
    print("Embeddings salvos.")

    # ETAPA 4: Encontrar e salvar matches
    print("[ETAPA 4] Encontrando e salvando matches...")
    from motor_ia import MotorDeCompatibilidade
    motor = MotorDeCompatibilidade(load_model=True)
    num_matches = motor.encontrar_e_salvar_matches()
    print(f"{num_matches} matches encontrados e salvos.")

    end_time = time.time()
    print(f"--- ATUALIZAÇÃO COMPLETA EM {end_time - start_time:.2f} SEGUNDOS ---")

if __name__ == "__main__":
    run_complete_update()