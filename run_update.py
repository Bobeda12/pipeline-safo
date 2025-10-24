import os
import time
import random
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from faker import Faker
from sentence_transformers import SentenceTransformer
from motor_ia import MotorDeCompatibilidade # Importa a classe já configurada
import traceback # Para log de erros

# --- Configuração do Banco de Dados ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi configurada.")

try:
    engine = create_engine(DATABASE_URL)
except Exception as e:
    print(f"Erro fatal ao criar engine SQLAlchemy: {e}")
    exit(1) # Aborta se não conseguir conectar ao DB

# --- Configurações de Geração de Dados ---
NUM_EDITAIS = 500 # Manter baixo para testes rápidos
NUM_LINHAS_PESQUISA = 200
NUM_USUARIOS = 10
fake = Faker('pt_BR')

# --- Base de Conhecimento (Mantida igual) ---
AREAS_CONHECIMENTO = [
    {"area": "Inteligência Artificial", "programa": "PPGIA", "substantivos": ["algoritmos", "redes neurais", "aprendizado de máquina"], "verbos": ["otimizar", "desenvolver", "implementar"], "adjetivos": ["inteligente", "preditivo", "autônomo"]},
    {"area": "Computação Quântica", "programa": "PPGCQ", "substantivos": ["qubits", "algoritmos quânticos", "criptografia pós-quântica"], "verbos": ["projetar", "simular", "construir"], "adjetivos": ["quântico", "seguro", "robusto"]},
    {"area": "Energias Renováveis", "programa": "PPGER", "substantivos": ["energia solar", "energia eólica", "biomassa"], "verbos": ["gerar", "armazenar", "distribuir"], "adjetivos": ["sustentável", "limpa", "renovável"]}
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
    # Adicionar outros campos simulados se necessário
    return titulo, texto_base + frase_elegibilidade

def run_complete_update():
    """
    Executa o pipeline: popula dados simulados, calcula embeddings e encontra matches no PostgreSQL.
    Assume que as tabelas JÁ EXISTEM no Supabase.
    """
    print("--- INICIANDO TAREFA DE ATUALIZAÇÃO COMPLETA (PostgreSQL) ---")
    start_time = time.time()

    # ETAPA 1: Limpar tabelas existentes (opcional, cuidado em produção!)
    print("[ETAPA 1] Limpando tabelas existentes (match, linha_ime, edital, users)...")
    try:
        with engine.connect() as connection:
            with connection.begin(): # Transação
                # Ordem reversa por causa das Foreign Keys (se existirem e forem restritivas)
                connection.execute(text("DELETE FROM match"))
                connection.execute(text("DELETE FROM linha_ime"))
                connection.execute(text("DELETE FROM edital"))
                connection.execute(text("DELETE FROM users"))
                # Opcional: Resetar sequências das chaves primárias autoincrement
                # connection.execute(text("ALTER SEQUENCE users_id_seq RESTART WITH 1"))
                # connection.execute(text("ALTER SEQUENCE linha_ime_id_seq RESTART WITH 1"))
        print("Tabelas limpas.")
    except Exception as e:
        print(f"Erro ao limpar tabelas (talvez não existam ainda?): {e}")
        # Continuar mesmo se der erro aqui pode ser aceitável na primeira execução

    # ETAPA 2: Popular com dados de teste
    print("[ETAPA 2] Gerando e inserindo dados simulados...")
    users = [('admin@ime.br', 'admin')] + [(f'user{i}@ime.br', '123') for i in range(2, NUM_USUARIOS + 1)]
    linhas_data = []
    for _ in range(NUM_LINHAS_PESQUISA):
        base = random.choice(AREAS_CONHECIMENTO)
        linha, desc = gerar_linha_pesquisa(base)
        user_id = random.randint(1, NUM_USUARIOS) # Assume que IDs de usuário começam em 1
        linhas_data.append((base['programa'], linha, desc, fake.email(), user_id))

    editais_data = []
    for i in range(1, NUM_EDITAIS + 1):
        base = random.choice(AREAS_CONHECIMENTO)
        titulo, texto_pdf = gerar_edital(base)
        # Adicionar dados simulados para as novas colunas
        prazo = fake.future_datetime(end_date='+60d') # Prazo em até 60 dias
        editais_data.append((
            i, titulo, "FINEP", fake.url(), texto_pdf, "aberto",
            random.choice(["Nacional", "Regional"]), # modalidade
            prazo, # prazo_submissao
            f"R$ {random.randint(50, 500)} mil", # valor_estimado
            random.choice(FRASES_ELEGIBILIDADE), # elegibilidade
            base['area'], # areas_tema
            pd.Timestamp.now(tz='UTC') # data_captura (agora)
        ))

    try:
        with engine.connect() as connection:
            with connection.begin(): # Transação para todas as inserções
                # Insere usuários
                connection.execute(text("INSERT INTO users (email, password) VALUES (:email, :password)"), [{"email": e, "password": p} for e, p in users])

                # Insere linhas (sem embedding ainda)
                connection.execute(text("""
                    INSERT INTO linha_ime (programa, linha, descricao, emails_contato, user_id)
                    VALUES (:programa, :linha, :descricao, :emails_contato, :user_id)
                """), [{"programa": p, "linha": l, "descricao": d, "emails_contato": ec, "user_id": uid} for p, l, d, ec, uid in linhas_data])

                # Insere editais (com novas colunas)
                connection.execute(text("""
                    INSERT INTO edital (id, titulo, orgao, link_pagina, texto_pdf, status, modalidade, prazo_submissao, valor_estimado, elegibilidade, areas_tema, data_captura)
                    VALUES (:id, :titulo, :orgao, :link_pagina, :texto_pdf, :status, :modalidade, :prazo_submissao, :valor_estimado, :elegibilidade, :areas_tema, :data_captura)
                """), [
                    {"id": i, "titulo": t, "orgao": o, "link_pagina": lk, "texto_pdf": txt, "status": s,
                     "modalidade": mod, "prazo_submissao": pz, "valor_estimado": val, "elegibilidade": el, "areas_tema": at, "data_captura": dc}
                    for i, t, o, lk, txt, s, mod, pz, val, el, at, dc in editais_data
                ])
        print(f"{len(users)} usuários, {len(linhas_data)} linhas, {len(editais_data)} editais inseridos.")
    except Exception as e:
        print(f"Erro CRÍTICO ao inserir dados: {e}")
        traceback.print_exc()
        exit(1) # Aborta se a inserção falhar

    # ETAPA 3: Calcular e salvar embeddings
    print("[ETAPA 3] Pré-calculando e salvando embeddings...")
    try:
        # Lê as linhas que acabamos de inserir para obter IDs e descrições
        df_linhas = pd.read_sql_query("SELECT id, descricao FROM linha_ime WHERE descricao IS NOT NULL AND descricao != ''", engine, index_col='id')
        if df_linhas.empty:
            print("Nenhuma linha de pesquisa encontrada para calcular embeddings.")
        else:
            print(f"Calculando embeddings para {len(df_linhas)} linhas...")
            model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            embeddings = model.encode(df_linhas['descricao'].tolist(), show_progress_bar=True)

            print("Salvando embeddings no banco de dados...")
            with engine.connect() as connection:
                with connection.begin():
                    for index, embedding in enumerate(embeddings):
                        linha_id = df_linhas.index[index]
                        # Converte para formato string '[1.2,3.4,...]' compatível com tipo 'vector' via SQL puro
                        embedding_str = '[' + ','.join(map(str, embedding.astype(np.float32))) + ']'
                        connection.execute(
                            text("UPDATE linha_ime SET embedding = :embedding WHERE id = :id"),
                            {"embedding": embedding_str, "id": int(linha_id)} # Garante que ID é int
                        )
            print("Embeddings salvos.")
    except ImportError:
        print("Erro: SentenceTransformers não instalado ou não encontrado.")
    except Exception as e:
        print(f"Erro durante cálculo ou salvamento de embeddings: {e}")
        traceback.print_exc()
        # Continuar mesmo se embeddings falharem? Decida a política.

    # ETAPA 4: Encontrar e salvar matches (usando a classe MotorDeCompatibilidade)
    print("[ETAPA 4] Encontrando e salvando matches...")
    try:
        # Instancia o motor em modo worker (carrega o modelo de IA)
        # Ele usará o engine PostgreSQL definido globalmente
        motor = MotorDeCompatibilidade(load_model=True)
        if motor.model: # Verifica se o modelo foi carregado com sucesso
            num_matches = motor.encontrar_e_salvar_matches()
            print(f"Processo de matches concluído. {num_matches} matches processados.")
        else:
            print("Modelo de IA não carregado, pulando cálculo de matches.")
    except Exception as e:
        print(f"Erro ao instanciar ou rodar MotorDeCompatibilidade para matches: {e}")
        traceback.print_exc()

    end_time = time.time()
    print(f"--- ATUALIZAÇÃO COMPLETA (PostgreSQL) CONCLUÍDA EM {end_time - start_time:.2f} SEGUNDOS ---")

if __name__ == "__main__":
    run_complete_update()
