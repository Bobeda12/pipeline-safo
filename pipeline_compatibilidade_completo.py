import pandas as pd
import numpy as np
import datetime
import time
import os # Biblioteca para interagir com o sistema operacional
from dotenv import load_dotenv # Para carregar nosso arquivo .env
from sqlalchemy import create_engine
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# --- CARREGAR VARIÁVEIS DE AMBIENTE ---
load_dotenv()

# --- CONFIGURAÇÕES GERAIS (Lidas do arquivo .env) ---
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Mapeamento de Colunas
COLUNA_EDITAL_STATUS = os.getenv("COLUNA_EDITAL_STATUS", "status")
COLUNA_EDITAL_ELEGIBILIDADE = os.getenv("COLUNA_EDITAL_ELEGIBILIDADE", "texto_pdf")
# COLUNA_EDITAL_PRAZO = os.getenv("COLUNA_EDITAL_PRAZO", "prazo_submissao") # Descomente quando a coluna existir

# Configurações da IA
TOP_N_POR_LINHA = 5
LIMIAR_MINIMO = 0.68

# --- CONSTRUÇÃO DA CONEXÃO COM O BANCO ---
def get_database_engine():
    """Cria a conexão do SQLAlchemy com base nas variáveis de ambiente."""
    if DB_TYPE == "sqlite":
        return create_engine(f'sqlite:///{DB_NAME}')
    elif DB_TYPE == "postgresql":
        # Exige: pip install psycopg2-binary
        return create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
    elif DB_TYPE == "mysql":
        # Exige: pip install mysqlclient
        return create_engine(f'mysql+mysqldb://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')
    else:
        raise ValueError("DB_TYPE não suportado no arquivo .env")

# (A função 'filtrar_por_elegibilidade' continua a mesma, mas agora usa a variável de configuração)
def filtrar_por_elegibilidade(df: pd.DataFrame) -> pd.DataFrame:
    PALAVRAS_CHAVE_POSITIVAS = ['ict', 'instituição de ciência', 'instituições de pesquisa', 'universidade', 'pública']
    PALAVRAS_CHAVE_NEGATIVAS = ['exclusivo para empresas', 'somente mei', 'apenas para startups']
    indices_para_manter = []
    
    for index, row in df.iterrows():
        # Usa a variável de configuração para encontrar a coluna certa
        texto = str(row[COLUNA_EDITAL_ELEGIBILIDADE]).lower()
        if any(palavra in texto for palavra in PALAVRAS_CHAVE_NEGATIVAS):
            continue
        if any(palavra in texto for palavra in PALAVRAS_CHAVE_POSITIVAS):
            indices_para_manter.append(index)
    return df.loc[indices_para_manter]


def pipeline_final():
    start_time = time.time()
    engine = get_database_engine()

    print(f"--- INICIANDO PIPELINE (CONECTANDO AO BANCO '{DB_TYPE}') ---")
    
    print("\n1. Carregando e aplicando filtros de regras aos editais...")
    df_editais = pd.read_sql_table('edital', engine)
    
    # Filtro de Status
    df_editais_abertos = df_editais[df_editais[COLUNA_EDITAL_STATUS] == 'aberto'].copy()
    
    # Filtro de Elegibilidade
    df_editais_elegiveis = filtrar_por_elegibilidade(df_editais_abertos)
    
    print(f" > {len(df_editais)} editais no total.")
    print(f" > {len(df_editais_abertos)} após filtro de status.")
    print(f" > {len(df_editais_elegiveis)} após filtro de elegibilidade.")

    if df_editais_elegiveis.empty:
        print("\nNenhum edital elegível encontrado. Encerrando.")
        return

    # O resto do pipeline continua exatamente o mesmo...
    print("\n2. Iniciando análise de IA...")
    df_linhas = pd.read_sql_table('linha_ime', engine)
    embeddings_linhas_precalculados = np.array([np.frombuffer(blob, dtype=np.float32) for blob in df_linhas['embedding']])
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    textos_editais = (df_editais_elegiveis['titulo'] + '. ' + df_editais_elegiveis[COLUNA_EDITAL_ELEGIBILIDADE]).tolist()
    embeddings_editais = model.encode(textos_editais, show_progress_bar=True)
    matriz_similaridade = cosine_similarity(embeddings_editais, embeddings_linhas_precalculados)

    print(f"\n3. Selecionando os TOP {TOP_N_POR_LINHA} melhores matches (score >= {LIMIAR_MINIMO})...")
    # ... (a lógica de seleção Top-N não muda) ...
    lista_matches = []
    for idx_linha, linha in df_linhas.iterrows():
        scores_para_esta_linha = matriz_similaridade[:, idx_linha]
        indices_top_n_editais = scores_para_esta_linha.argsort()[-TOP_N_POR_LINHA:][::-1]
        for idx_edital_na_matriz in indices_top_n_editais:
            score = scores_para_esta_linha[idx_edital_na_matriz]
            if score >= LIMIAR_MINIMO:
                edital = df_editais_elegiveis.iloc[idx_edital_na_matriz]
                match = {'edital_id': edital['id'], 'linha_id': linha['id'], 'score': round(float(score), 4),
                         'data_calculo': datetime.datetime.now(), 'notificado': False}
                lista_matches.append(match)

    if not lista_matches:
        print("\nNenhum match encontrado com os critérios atuais.")
    else:
        df_matches = pd.DataFrame(lista_matches).drop_duplicates()
        df_matches.to_sql('match', engine, if_exists='replace', index=False)
        print(f"\n--- {len(df_matches)} RESULTADOS SALVOS NA TABELA 'match' ---")

    end_time = time.time()
    print(f"\nPipeline concluído em {end_time - start_time:.2f} segundos.")

if __name__ == '__main__':
    pipeline_final()