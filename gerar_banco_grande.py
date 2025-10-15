# gerar_banco_grande.py
import sqlite3
import random
import time
from faker import Faker

# --- CONFIGURAÇÕES ---
NOME_BANCO = 'projeto_grande.db'
NUM_EDITAIS = 500 # Usando um número menor para testes mais rápidos
NUM_LINHAS_PESQUISA = 200

fake = Faker('pt_BR')

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
    },
    {
        "area": "Defesa Cibernética", "programa": "PPGDC",
        "substantivos": ["segurança de redes", "criptografia", "detecção de intrusão", "malware", "defesa ativa"],
        "verbos": ["proteger", "monitorar", "defender", "analisar", "mitigar"],
        "adjetivos": ["seguro", "resiliente", "cibernético", "estratégico", "confiável"]
    }
]

FRASES_ELEGIBILIDADE = [
    "Este edital é aberto a toda instituição de ciência e tecnologia (ICT) do país.",
    "Universidades públicas e institutos de pesquisa são o público-alvo principal.",
    "Podem se inscrever pesquisadores vinculados a qualquer instituição de pesquisa nacional.",
    "Esta chamada é de uso exclusivo para empresas de base tecnológica e startups.",
    "Apenas startups e MEI podem se inscrever nesta oportunidade de fomento.",
    "Os critérios de elegibilidade estão detalhados no anexo IV do documento oficial.",
    "Proponentes devem consultar a seção 3.1 para detalhes completos de elegibilidade."
]

def gerar_linha_pesquisa(base):
    linha = f"Estudo de {random.choice(base['substantivos'])} e {random.choice(base['substantivos'])}"
    descricao = f"Análise e desenvolvimento de sistemas {base['adjetivos'][0]} para {base['area']}, com foco em {random.choice(base['substantivos'])}. A pesquisa busca {random.choice(base['verbos'])} modelos {base['adjetivos'][1]}."
    return linha, descricao

def gerar_edital(base):
    titulo = f"Chamada Pública nº {random.randint(1, 99)}/2025 - Fomento a Projetos em {base['area']}"
    texto_base = f"O presente edital visa selecionar propostas para apoio financeiro a projetos que contribuam para o desenvolvimento científico e tecnológico em {base['area']}. Serão consideradas propostas que busquem {random.choice(base['verbos'])} soluções em {random.choice(base['substantivos'])}. "
    frase_elegibilidade_aleatoria = random.choice(FRASES_ELEGIBILIDADE)
    texto_pdf = texto_base + " " + frase_elegibilidade_aleatoria
    return titulo, texto_pdf

def criar_banco_grande():
    print(f"Iniciando a criação do banco de dados '{NOME_BANCO}' com dados realistas e elegibilidade...")
    start_time = time.time()
    
    conn = sqlite3.connect(NOME_BANCO)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS edital;")
    cursor.execute("DROP TABLE IF EXISTS linha_ime;")
    cursor.execute("DROP TABLE IF EXISTS match;")
    
    cursor.execute("CREATE TABLE edital (id INTEGER PRIMARY KEY, titulo TEXT, orgao TEXT, link_pagina TEXT, texto_pdf TEXT, status TEXT);")
    cursor.execute("CREATE TABLE linha_ime (id INTEGER PRIMARY KEY, programa TEXT, linha TEXT, descricao TEXT, emails_contato TEXT, embedding BLOB);")
    
    # Gerar Linhas de Pesquisa
    print(f"Gerando {NUM_LINHAS_PESQUISA} linhas de pesquisa...")
    linhas_para_inserir = []
    for i in range(1, NUM_LINHAS_PESQUISA + 1):
        base = random.choice(AREAS_CONHECIMENTO)
        linha, descricao = gerar_linha_pesquisa(base)
        # Inserindo None para o embedding, que será calculado depois
        linhas_para_inserir.append((i, base['programa'], linha, descricao, fake.email(), None))
    cursor.executemany("INSERT INTO linha_ime VALUES (?, ?, ?, ?, ?, ?);", linhas_para_inserir)
    
    # Gerar Editais
    print(f"Gerando {NUM_EDITAIS} editais...")
    editais_para_inserir = []
    for i in range(1, NUM_EDITAIS + 1):
        base = random.choice(AREAS_CONHECIMENTO)
        titulo, texto_pdf = gerar_edital(base)
        editais_para_inserir.append((i, titulo, "FINEP", fake.url(), texto_pdf, "aberto"))
    cursor.executemany("INSERT INTO edital VALUES (?, ?, ?, ?, ?, ?);", editais_para_inserir)

    conn.commit()
    conn.close()
    
    end_time = time.time()
    print("\nConcluído!")
    print(f"Banco de dados '{NOME_BANCO}' criado com sucesso.")
    print(f" > {NUM_LINHAS_PESQUISA} linhas de pesquisa inseridas.")
    print(f" > {NUM_EDITAIS} editais inseridos.")
    print(f"Tempo total: {end_time - start_time:.2f} segundos.")

if __name__ == '__main__':
    criar_banco_grande()