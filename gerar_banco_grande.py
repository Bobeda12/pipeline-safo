# gerar_banco_grande.py
import sqlite3
import random
import time
from faker import Faker
import os

# --- CONFIGURAÇÕES ---
NOME_BANCO = os.getenv("DB_NAME", "projeto_grande.db")
NUM_EDITAIS = 500
NUM_LINHAS_PESQUISA = 200
NUM_USUARIOS = 10

fake = Faker('pt_BR')

# --- BASE DE CONHECIMENTO ---
AREAS_CONHECIMENTO = [
    {
        "area": "Inteligência Artificial", "programa": "PPGIA",
        "substantivos": ["algoritmos", "redes neurais", "aprendizado de máquina", "processamento de linguagem natural", "visão computacional"],
        "verbos": ["otimizar", "desenvolver", "implementar", "analisar", "automatizar"],
        "adjetivos": ["inteligente", "preditivo", "autônomo", "eficiente", "escalável"]
    },
    {
        "area": "Computação Quântica", "programa": "PPGCQ",
        "substantivos": ["qubits", "algoritmos quânticos", "criptografia pós-quântica", "hardware quântico", "simulação de sistemas"],
        "verbos": ["projetar", "simular", "construir", "proteger", "acelerar"],
        "adjetivos": ["quântico", "seguro", "robusto", "inovador", "disruptivo"]
    },
    {
        "area": "Energias Renováveis", "programa": "PPGER",
        "substantivos": ["energia solar", "energia eólica", "biomassa", "células fotovoltaicas", "redes inteligentes"],
        "verbos": ["gerar", "armazenar", "distribuir", "integrar", "sustentar"],
        "adjetivos": ["sustentável", "limpa", "renovável", "eficiente", "verde"]
    },
    {
        "area": "Biotecnologia", "programa": "PPGBIO",
        "substantivos": ["engenharia genética", "terapias celulares", "biofármacos", "diagnóstico molecular", "biologia sintética"],
        "verbos": ["sintetizar", "diagnosticar", "tratar", "modificar", "cultivar"],
        "adjetivos": ["molecular", "genético", "terapêutico", "inovador", "biológico"]
    }
]
FRASES_ELEGIBILIDADE = [
    "Este edital é aberto a toda instituição de ciência e tecnologia (ICT) do país.",
    "Universidades públicas e institutos de pesquisa são o público-alvo principal.",
    "Podem se inscrever pesquisadores vinculados a qualquer instituição de pesquisa nacional.",
    "Esta chamada é de uso exclusivo para empresas de base tecnológica e startups.",
    "Apenas startups e MEI podem se inscrever nesta oportunidade de fomento."
]

def gerar_linha_pesquisa(base):
    linha = f"Estudo de {random.choice(base['substantivos'])} e {random.choice(base['substantivos'])}"
    descricao = f"Análise e desenvolvimento de sistemas {base['adjetivos'][0]} para {base['area']}, com foco em {random.choice(base['substantivos'])}. A pesquisa busca {random.choice(base['verbos'])} modelos {base['adjetivos'][1]}."
    return linha, descricao

def gerar_edital(base):
    titulo = f"Chamada Pública nº {random.randint(1, 99)}/2025 - Fomento a Projetos em {base['area']}"
    texto_base = f"O presente edital visa selecionar propostas para apoio financeiro a projetos... Serão consideradas propostas que busquem {random.choice(base['verbos'])} soluções em {random.choice(base['substantivos'])}. "
    frase_elegibilidade_aleatoria = random.choice(FRASES_ELEGIBILIDADE)
    texto_pdf = texto_base + " " + frase_elegibilidade_aleatoria
    return titulo, texto_pdf

def criar_banco_grande():
    print(f"Iniciando a criação do banco de dados '{NOME_BANCO}'...")
    if os.path.exists(NOME_BANCO):
        os.remove(NOME_BANCO)
    
    conn = sqlite3.connect(NOME_BANCO)
    cursor = conn.cursor()

    # Criação de Tabelas
    cursor.execute("CREATE TABLE edital (id INTEGER PRIMARY KEY, titulo TEXT, orgao TEXT, link_pagina TEXT, texto_pdf TEXT, status TEXT);")
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);")
    cursor.execute("""
        CREATE TABLE linha_ime (
            id INTEGER PRIMARY KEY AUTOINCREMENT, programa TEXT, linha TEXT, descricao TEXT, 
            emails_contato TEXT, embedding BLOB, user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    print("Tabelas criadas com sucesso.")

    # Geração de Utilizadores
    print(f"Gerando {NUM_USUARIOS} utilizadores de teste...")
    utilizadores_para_inserir = [('admin@ime.br', 'admin')]
    for i in range(2, NUM_USUARIOS + 1):
        utilizadores_para_inserir.append((f'user{i}@ime.br', '123'))
    cursor.executemany("INSERT OR IGNORE INTO users (email, password) VALUES (?, ?);", utilizadores_para_inserir)

    # Geração de Linhas de Pesquisa
    print(f"Gerando {NUM_LINHAS_PESQUISA} linhas de pesquisa...")
    linhas_para_inserir = []
    for _ in range(NUM_LINHAS_PESQUISA):
        base = random.choice(AREAS_CONHECIMENTO)
        linha, descricao = gerar_linha_pesquisa(base)
        user_id_aleatorio = random.randint(1, NUM_USUARIOS)
        linhas_para_inserir.append((base['programa'], linha, descricao, fake.email(), user_id_aleatorio))
    cursor.executemany("INSERT INTO linha_ime (programa, linha, descricao, emails_contato, user_id) VALUES (?, ?, ?, ?, ?);", linhas_para_inserir)

    # Geração de Editais
    print(f"Gerando {NUM_EDITAIS} editais...")
    editais_para_inserir = []
    for i in range(1, NUM_EDITAIS + 1):
        base = random.choice(AREAS_CONHECIMENTO)
        titulo, texto_pdf = gerar_edital(base)
        editais_para_inserir.append((i, titulo, "FINEP", fake.url(), texto_pdf, "aberto"))
    cursor.executemany("INSERT INTO edital VALUES (?, ?, ?, ?, ?, ?);", editais_para_inserir)

    conn.commit()
    conn.close()
    print("Banco de dados populado com sucesso.")

if __name__ == '__main__':
    criar_banco_grande()