# pre_calcular_embeddings_ime.py
import pandas as pd
import numpy as np
import sqlite3
from sqlalchemy import create_engine
from sentence_transformers import SentenceTransformer
import os

NOME_BANCO_DADOS = os.getenv("DB_NAME", "projeto_grande.db")

def gerar_e_salvar_embeddings_ime():
    engine = create_engine(f'sqlite:///{NOME_BANCO_DADOS}')
    df_linhas = pd.read_sql_table('linha_ime', engine)

    print("Carregando modelo de embedding...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    print("Gerando embeddings para as linhas de pesquisa do IME...")
    textos_linhas = df_linhas['descricao'].tolist()
    embeddings_linhas = model.encode(textos_linhas, show_progress_bar=True)
    
    print("Salvando embeddings no banco de dados...")
    conn = sqlite3.connect(NOME_BANCO_DADOS)
    cursor = conn.cursor()
    
    for index, embedding in enumerate(embeddings_linhas):
        linha_id = int(df_linhas.iloc[index]['id'])
        embedding_blob = embedding.astype(np.float32).tobytes()
        cursor.execute("UPDATE linha_ime SET embedding = ? WHERE id = ?", (embedding_blob, linha_id))

    conn.commit()
    conn.close()
    print("Embeddings das linhas do IME salvos com sucesso!")

if __name__ == '__main__':
    gerar_e_salvar_embeddings_ime()